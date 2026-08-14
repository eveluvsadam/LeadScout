"""LeadScout — FastAPI application.

Serves a plain HTML dashboard plus a small REST API. A search geocodes the
location, pulls businesses from OpenStreetMap, analyses each website, scores
it, and stores the leads in SQLite.
"""
import asyncio
import base64
import hashlib
import io
import json
import secrets
import zipfile
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .config import APP_PASSWORD

import time

from . import database as db
from . import export as exporter
from . import mailer
from . import osm
from . import sales
from . import website
from .analyze import analyze_site, classify_opportunity
from .config import (MAX_BUSINESSES, MAX_BUSINESSES_STATE, ANALYZE_CONCURRENCY,
                     MAX_BATCH_SEND, SEND_DELAY_SECONDS)
from .recommend import build_recommendation

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="LeadScout", version="2.0.0")


class PasswordGate(BaseHTTPMiddleware):
    """When APP_PASSWORD is set, require it (HTTP Basic) on every page.
    Health checks and static assets stay open so hosting platforms work."""
    async def dispatch(self, request, call_next):
        if not APP_PASSWORD:
            return await call_next(request)
        path = request.url.path
        if path == "/healthz" or path.startswith("/static"):
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                if secrets.compare_digest(pw, APP_PASSWORD):
                    return await call_next(request)
            except Exception:
                pass
        return Response("Authentication required", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="LeadScout"'})


app.add_middleware(PasswordGate)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    from .config import ADMIN_RESET
    if ADMIN_RESET:
        db.reset_admin()
        print("ADMIN_RESET is set: admin password cleared. Remove ADMIN_RESET now.")


# --------------------------------------------------------------------------- #
#  Core: run a search and persist leads                                        #
# --------------------------------------------------------------------------- #
async def run_search(city: str, state: str, country: str, categories: list[str],
                     whole_state: bool = False, radius_km: float | None = None) -> dict:
    """Geocode -> OSM lookup -> analyse -> score -> store. Returns a summary.

    `categories` may hold one or several category names (or "All categories").
    `radius_km`, if set, searches within that radius of the location's centre
    instead of using a city/state bounding box.
    """
    categories = [c for c in categories if c and c.strip()]
    if not categories:
        return {"error": "Choose at least one category, or type one in the box."}
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
        businesses = await osm.search_businesses(
            bbox, categories, radius_km=radius_km if not whole_state else None, limit=cap)
    except Exception:
        return {"error": "Business data servers are busy right now. Please try again in a moment."}
    businesses = businesses[:cap]

    label = categories[0] if len(categories) == 1 else "Multiple"
    search_id = db.create_search(city, state, country, label)

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
        "all_categories": osm.ALL_CATEGORIES,
        "stats": db.stats(),
        "mail_ready": mailer.is_configured(),
        "leads": db.query_leads(
            opportunity=extra.get("opportunity"),
            has_website=extra.get("has_website"),
            category=extra.get("category"),
            callable_only=extra.get("callable_only", False),
        ),
    }
    ctx.update(extra)
    return templates.TemplateResponse("index.html", ctx)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, opportunity: str = "", has_website: str = "",
         category: str = "", callable_only: str = ""):
    hw = None if has_website == "" else (has_website == "1")
    return _render(request, opportunity=opportunity or None,
                   has_website=hw, category=category or None,
                   callable_only=(callable_only == "1"),
                   filter_opportunity=opportunity, filter_haswebsite=has_website,
                   filter_category=category, filter_callable=callable_only)


def _collect_categories(form_categories: list[str], custom: str,
                        all_cats: str) -> list[str]:
    if all_cats == "1":
        return [osm.ALL_CATEGORIES]
    cats = list(form_categories)
    if custom.strip():
        cats.append(custom.strip())
    return cats


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, city: str = Form(""), state: str = Form(""),
                 country: str = Form(""), category: list[str] = Form([]),
                 custom_category: str = Form(""), whole_state: str = Form(""),
                 all_categories: str = Form(""), radius_km: str = Form("")):
    cats = _collect_categories(category, custom_category, all_categories)
    try:
        radius = float(radius_km) if radius_km.strip() else None
    except ValueError:
        radius = None
    result = await run_search(city.strip(), state.strip(), country.strip(),
                              cats, whole_state=whole_state == "1", radius_km=radius)
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
        "packages": get_packages(),
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
#  Batch email sending (only the leads you selected; never automatic)          #
# --------------------------------------------------------------------------- #
@app.post("/send-batch", response_class=HTMLResponse)
def send_batch(request: Request, lead_ids: list[int] = Form([])):
    if not mailer.is_configured():
        return _render(request, message={
            "error": "Email sending isn't set up. Add SELLER_EMAIL and "
                     "SELLER_EMAIL_APP_PASSWORD to your .env (see the note above)."})

    leads = db.get_leads_by_ids(lead_ids)
    # Only send to leads that actually have an email and haven't been emailed yet.
    targets = [l for l in leads if l.get("email") and not l.get("emailed_at")]
    targets = targets[:MAX_BATCH_SEND]

    sent, failed = 0, 0
    first_error = ""
    for i, lead in enumerate(targets):
        try:
            e = sales.generate_email(lead)
            mailer.send_email(lead["email"], e["subject"], e["body"])
            db.mark_emailed(lead["id"])
            sent += 1
        except Exception as exc:
            failed += 1
            if not first_error:
                first_error = str(exc)
        if i < len(targets) - 1:
            time.sleep(SEND_DELAY_SECONDS)   # be gentle with the mail server

    msg = {"sent": sent, "failed": failed, "skipped": len(leads) - len(targets)}
    if failed and first_error:
        msg["error"] = f"{failed} failed to send. First error: {first_error}"
    return _render(request, send_result=msg)


# --------------------------------------------------------------------------- #
#  Admin dashboard: manage searches, leads, sent emails, package pricing       #
# --------------------------------------------------------------------------- #
def get_packages() -> list:
    raw = db.get_setting("packages")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return sales.DEFAULT_PACKAGES


# ---- Admin password (set on first use, stored hashed in the DB, never in git) #
def _admin_password_set() -> bool:
    return bool(db.get_setting("admin_pw_hash"))


def _set_admin_password(pw: str) -> None:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    db.set_setting("admin_pw_salt", salt)
    db.set_setting("admin_pw_hash", h)


def _verify_admin_password(pw: str) -> bool:
    salt, h = db.get_setting("admin_pw_salt"), db.get_setting("admin_pw_hash")
    if not salt or not h:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return secrets.compare_digest(calc, h)


def _new_admin_session() -> str:
    token = secrets.token_urlsafe(32)
    db.set_setting("admin_session", token)
    return token


def _admin_authed(request: Request) -> bool:
    token = db.get_setting("admin_session")
    cookie = request.cookies.get("admin_session")
    return bool(token and cookie and secrets.compare_digest(cookie, token))


def _login_cookie(token: str) -> Response:
    r = Response(status_code=303, headers={"Location": "/admin"})
    r.set_cookie("admin_session", token, httponly=True, samesite="lax",
                 max_age=60 * 60 * 24 * 30)
    return r


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    # First run anywhere (fresh clone/deploy): no password set yet -> set one.
    if not _admin_password_set():
        return templates.TemplateResponse("admin_gate.html",
                                          {"request": request, "setup": True})
    if not _admin_authed(request):
        return templates.TemplateResponse("admin_gate.html",
                                          {"request": request, "setup": False})
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": db.stats(),
        "searches": db.list_searches(),
        "emailed": db.query_leads(emailed_only=True, limit=500),
        "packages": get_packages(),
        "mail_ready": mailer.is_configured(),
        "seller": {
            "name": sales.SELLER_NAME, "company": sales.SELLER_COMPANY,
            "phone": sales.SELLER_PHONE, "email": sales.SELLER_EMAIL,
        },
        "db_kind": "PostgreSQL" if "postgresql" in str(db.engine.url) else "SQLite",
    })


@app.post("/admin/setup")
def admin_setup(request: Request, password: str = Form(...), confirm: str = Form("")):
    if _admin_password_set():   # already set — don't allow silent reset
        return Response(status_code=303, headers={"Location": "/admin"})
    if len(password) < 6 or password != confirm:
        return templates.TemplateResponse("admin_gate.html", {
            "request": request, "setup": True,
            "error": "Passwords must match and be at least 6 characters."})
    _set_admin_password(password)
    return _login_cookie(_new_admin_session())


@app.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)):
    if not _verify_admin_password(password):
        return templates.TemplateResponse("admin_gate.html", {
            "request": request, "setup": False, "error": "Wrong password."})
    return _login_cookie(_new_admin_session())


@app.post("/admin/logout")
def admin_logout():
    db.set_setting("admin_session", "")   # invalidates the cookie everywhere
    r = Response(status_code=303, headers={"Location": "/admin"})
    r.delete_cookie("admin_session")
    return r


@app.post("/admin/delete-search")
def admin_delete_search(request: Request, search_id: int = Form(...)):
    if not _admin_authed(request):
        return Response(status_code=303, headers={"Location": "/admin"})
    db.delete_search(search_id)
    return Response(status_code=303, headers={"Location": "/admin"})


@app.post("/admin/delete-all")
def admin_delete_all(request: Request):
    if not _admin_authed(request):
        return Response(status_code=303, headers={"Location": "/admin"})
    db.delete_all_leads()
    return Response(status_code=303, headers={"Location": "/admin"})


@app.post("/admin/packages")
def admin_packages(request: Request, name: list[str] = Form([]),
                   price: list[str] = Form([]), features: list[str] = Form([])):
    if not _admin_authed(request):
        return Response(status_code=303, headers={"Location": "/admin"})
    packages = []
    for i, nm in enumerate(name):
        try:
            pr = int(float(price[i]))
        except (ValueError, IndexError):
            pr = 0
        feats = [f.strip() for f in (features[i] if i < len(features) else "").splitlines() if f.strip()]
        packages.append({"name": nm, "price": pr, "features": feats})
    db.set_setting("packages", json.dumps(packages))
    return Response(status_code=303, headers={"Location": "/admin"})


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
                     country: str = Form(""), category: list[str] = Form([]),
                     custom_category: str = Form(""), whole_state: str = Form(""),
                     all_categories: str = Form(""), radius_km: str = Form("")):
    cats = _collect_categories(category, custom_category, all_categories)
    try:
        radius = float(radius_km) if radius_km.strip() else None
    except ValueError:
        radius = None
    result = await run_search(city.strip(), state.strip(), country.strip(),
                              cats, whole_state=whole_state == "1", radius_km=radius)
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
