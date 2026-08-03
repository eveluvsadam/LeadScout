"""LeadScout — FastAPI application.

Serves a plain HTML dashboard plus a small REST API. A search geocodes the
location, pulls businesses from OpenStreetMap, analyses each website, scores
it, and stores the leads in SQLite.
"""
import asyncio
import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import database as db
from . import export as exporter
from . import osm
from . import sales
from . import website
from .analyze import analyze_site, classify_opportunity
from .config import MAX_BUSINESSES, MAX_BUSINESSES_STATE, ANALYZE_CONCURRENCY
from .recommend import build_recommendation

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="LeadScout", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# --------------------------------------------------------------------------- #
#  Core: run a search and persist leads                                        #
# --------------------------------------------------------------------------- #
async def run_search(city: str, state: str, country: str, category: str,
                     whole_state: bool = False) -> dict:
    """Geocode -> OSM lookup -> analyse -> score -> store. Returns a summary."""
    if not category.strip():
        return {"error": "Choose a category or type one in the box."}
    if whole_state and not state:
        return {"error": "Enter a state/province to scan the whole state."}
    if not whole_state and not city:
        return {"error": "Enter a city, or tick 'Search the whole state'."}

    cap = MAX_BUSINESSES_STATE if whole_state else MAX_BUSINESSES
    try:
        bbox = await osm.geocode(city, state, country, whole_state=whole_state)
    except Exception:
        return {"error": "Location lookup service is temporarily unavailable. Please try again."}
    if not bbox:
        where = state if whole_state else f"{city}, {state}, {country}"
        return {"error": f"Could not find location: {where}. Check the spelling."}

    try:
        businesses = await osm.find_businesses(bbox, category, limit=cap)
    except Exception:
        return {"error": "Business data servers are busy right now. Please try again in a moment."}
    businesses = businesses[:cap]

    search_id = db.create_search(city, state, country, category)

    sem = asyncio.Semaphore(ANALYZE_CONCURRENCY)

    async def process(biz: dict) -> dict:
        async with sem:
            analysis = await analyze_site(biz.get("website"))
        has_site = bool(biz.get("website")) and analysis["reachable"]
        lead = {
            **biz,
            "search_id": search_id,
            "has_website": 1 if has_site else 0,
            "https": 1 if analysis["https"] else 0,
            "mobile_friendly": 1 if analysis["mobile_friendly"] else 0,
            "meta_title": analysis["meta_title"],
            "meta_description": analysis["meta_description"],
            "load_ms": analysis["load_ms"],
            "broken_links": analysis["broken_links"],
            "website_score": analysis["website_score"],
            "seo_score": analysis["seo_score"],
            "modernization_score": analysis["modernization_score"],
            "opportunity": classify_opportunity(bool(biz.get("website")), analysis),
        }
        lead["recommendation"] = build_recommendation(biz, analysis)
        return lead

    leads = await asyncio.gather(*(process(b) for b in businesses))
    db.insert_leads(leads)                      # one bulk write, not one per lead
    db.set_search_count(search_id, len(businesses))
    return {"search_id": search_id, "count": len(businesses)}


# --------------------------------------------------------------------------- #
#  HTML frontend                                                               #
# --------------------------------------------------------------------------- #
def _render(request, **extra):
    ctx = {
        "request": request,
        "categories": osm.CATEGORIES,
        "stats": db.stats(),
        "leads": db.query_leads(
            opportunity=extra.get("opportunity"),
            has_website=extra.get("has_website"),
            category=extra.get("category"),
        ),
    }
    ctx.update(extra)
    return templates.TemplateResponse("index.html", ctx)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, opportunity: str = "", has_website: str = "",
         category: str = ""):
    hw = None if has_website == "" else (has_website == "1")
    return _render(request, opportunity=opportunity or None,
                   has_website=hw, category=category or None,
                   filter_opportunity=opportunity, filter_haswebsite=has_website,
                   filter_category=category)


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, city: str = Form(""), state: str = Form(""),
                 country: str = Form(""), category: str = Form(""),
                 custom_category: str = Form(""), whole_state: str = Form("")):
    effective = custom_category.strip() or category
    result = await run_search(city.strip(), state.strip(), country.strip(),
                              effective, whole_state=whole_state == "1")
    return _render(request, message=result)


# --------------------------------------------------------------------------- #
#  Sales workflow: per-lead email, report, demo website                        #
# --------------------------------------------------------------------------- #
_OVERRIDE_KEYS = {"color", "headline", "tagline", "phone", "email", "address",
                  "hours", "r1", "r1by", "r2", "r2by", "r3", "r3by",
                  "hero", "img1", "img2", "img3"}


def _overrides(request: Request) -> dict:
    return {k: v for k, v in request.query_params.items()
            if k in _OVERRIDE_KEYS and v.strip()}


@app.get("/lead/{lead_id}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        return HTMLResponse("Lead not found.", status_code=404)
    script = sales.call_script(lead)
    return templates.TemplateResponse("lead.html", {
        "request": request,
        "lead": lead,
        "email": sales.generate_email(lead),
        "report": sales.opportunity_report(lead),
        "packages": sales.DEFAULT_PACKAGES,
        "pages": website.page_structure(lead.get("category") or ""),
        "script": script,
        "script_text": sales.script_to_text(script),
    })


@app.get("/lead/{lead_id}/demo", response_class=HTMLResponse)
def lead_demo(request: Request, lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        return HTMLResponse("Lead not found.", status_code=404)
    site = website.generate_site(lead, _overrides(request))
    return HTMLResponse(site["inline"])


@app.get("/lead/{lead_id}/demo.zip")
def lead_demo_zip(request: Request, lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        return Response("Lead not found.", status_code=404)
    site = website.generate_site(lead, _overrides(request))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", site["html"])
        z.writestr("style.css", site["css"])
        z.writestr("script.js", site["js"])
        z.writestr("README.md", site["readme"])
        z.writestr("DEPLOY.md", site["deploy"])
    fname = f"{website.slug(lead.get('name'))}-website.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.get("/lead/{lead_id}/email.txt")
def lead_email_txt(lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        return Response("Lead not found.", status_code=404)
    e = sales.generate_email(lead)
    text = f"Subject: {e['subject']}\n\n{e['body']}\n"
    fname = f"{website.slug(lead.get('name'))}-email.txt"
    return Response(text, media_type="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


# --------------------------------------------------------------------------- #
#  Exports                                                                     #
# --------------------------------------------------------------------------- #
@app.get("/export/csv")
def export_csv(opportunity: str = "", has_website: str = "", category: str = ""):
    hw = None if has_website == "" else (has_website == "1")
    leads = db.query_leads(opportunity=opportunity or None, has_website=hw,
                           category=category or None, limit=100000)
    return Response(exporter.to_csv(leads), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=leads.csv"})


@app.get("/export/xlsx")
def export_xlsx(opportunity: str = "", has_website: str = "", category: str = ""):
    hw = None if has_website == "" else (has_website == "1")
    leads = db.query_leads(opportunity=opportunity or None, has_website=hw,
                           category=category or None, limit=100000)
    return Response(
        exporter.to_xlsx(leads),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads.xlsx"},
    )


# --------------------------------------------------------------------------- #
#  REST API (JSON)                                                             #
# --------------------------------------------------------------------------- #
@app.post("/api/search")
async def api_search(city: str = Form(""), state: str = Form(""),
                     country: str = Form(""), category: str = Form(""),
                     custom_category: str = Form(""), whole_state: str = Form("")):
    effective = custom_category.strip() or category
    result = await run_search(city.strip(), state.strip(), country.strip(),
                              effective, whole_state=whole_state == "1")
    status = 400 if "error" in result else 200
    return JSONResponse(result, status_code=status)


@app.get("/api/leads")
def api_leads(opportunity: str = "", has_website: str = "", category: str = "",
              search_id: int | None = None):
    hw = None if has_website == "" else (has_website == "1")
    return db.query_leads(opportunity=opportunity or None, has_website=hw,
                          category=category or None, search_id=search_id)


@app.get("/api/stats")
def api_stats():
    return db.stats()


@app.get("/api/categories")
def api_categories():
    return osm.CATEGORIES


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
