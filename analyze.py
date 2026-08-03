"""Fetch a business website and score it.

All checks are done by actually downloading the page (no paid API):
  - HTTPS / valid SSL          - meta title & description
  - mobile viewport            - H1 presence
  - load time                  - broken-link sample
  - HTML5 doctype / charset    - basic accessibility (lang, image alt text)

Produces three 0-100 scores (website, SEO, modernization) plus the raw
findings used to write a sales recommendation.
"""
import asyncio
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import SITE_TIMEOUT, CHECK_BROKEN_LINKS, MAX_PAGE_BYTES

# Empty analysis used when a lead has no website at all.
NO_SITE = {
    "reachable": False, "https": False, "mobile_friendly": False,
    "meta_title": None, "meta_description": None, "has_h1": False,
    "html5": False, "has_lang": False, "img_alt_ratio": None,
    "load_ms": None, "broken_links": None,
    "website_score": 0, "seo_score": 0, "modernization_score": 0,
}


def _clamp(v: int) -> int:
    return max(0, min(100, int(round(v))))


async def _check_broken_links(client, base_url, soup, limit=4) -> int | None:
    """HEAD a small sample of same-site links concurrently; return count failing."""
    if not CHECK_BROKEN_LINKS:
        return None
    origin = urlparse(base_url).netloc
    seen, targets = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        p = urlparse(href)
        if p.scheme not in ("http", "https") or p.netloc != origin or href in seen:
            continue
        seen.add(href)
        targets.append(href)
        if len(targets) >= limit:
            break

    async def check(href) -> bool:
        try:
            r = await client.head(href, timeout=4, follow_redirects=True)
            if r.status_code >= 400:  # some servers reject HEAD; confirm with GET
                r = await client.get(href, timeout=4, follow_redirects=True)
            return r.status_code >= 400
        except Exception:
            return True

    results = await asyncio.gather(*(check(h) for h in targets))
    return sum(1 for failed in results if failed)


async def analyze_site(url: str) -> dict:
    """Return an analysis dict for a website URL."""
    if not url:
        return dict(NO_SITE)
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    result = dict(NO_SITE)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadScout/1.0)"}
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=SITE_TIMEOUT, follow_redirects=True,
                                     headers=headers) as client:
            # Stream the page but stop after MAX_PAGE_BYTES — enough for the
            # <head> and page structure, without downloading megabytes.
            async with client.stream("GET", url) as resp:
                status = resp.status_code
                final_url = str(resp.url)
                encoding = resp.encoding or "utf-8"
                chunks, total = [], 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= MAX_PAGE_BYTES:
                        break
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            html = b"".join(chunks).decode(encoding, "replace")
            soup = BeautifulSoup(html, "html.parser")

            result["reachable"] = status < 400
            result["https"] = final_url.startswith("https://")
            result["load_ms"] = elapsed_ms

            # meta viewport => mobile friendly
            vp = soup.find("meta", attrs={"name": "viewport"})
            result["mobile_friendly"] = vp is not None

            title = soup.find("title")
            result["meta_title"] = title.get_text(strip=True) if title else None
            desc = soup.find("meta", attrs={"name": "description"})
            result["meta_description"] = desc.get("content", "").strip() if desc else None

            result["has_h1"] = soup.find("h1") is not None
            result["html5"] = html.lstrip()[:15].lower().startswith("<!doctype html>")
            result["has_lang"] = bool(soup.find("html", attrs={"lang": True}))

            imgs = soup.find_all("img")
            if imgs:
                with_alt = sum(1 for i in imgs if i.get("alt"))
                result["img_alt_ratio"] = round(with_alt / len(imgs), 2)

            result["broken_links"] = await _check_broken_links(client, final_url, soup)
    except httpx.ConnectError:
        return dict(NO_SITE)  # domain listed but site is dead => treat as no site
    except Exception:
        # Reachable-but-errored: keep whatever we have; scores stay low.
        result["reachable"] = result["reachable"]

    _score(result)
    return result


def _speed_points(load_ms, max_points) -> float:
    if load_ms is None:
        return 0
    if load_ms <= 800:
        return max_points
    if load_ms <= 1500:
        return max_points * 0.8
    if load_ms <= 3000:
        return max_points * 0.5
    if load_ms <= 5000:
        return max_points * 0.25
    return 0


def _score(r: dict) -> None:
    if not r["reachable"]:
        r["website_score"] = r["seo_score"] = r["modernization_score"] = 0
        return

    # ---- Website score (overall health) ----
    ws = 0
    ws += 20 if r["https"] else 0
    ws += 20 if r["mobile_friendly"] else 0
    ws += _speed_points(r["load_ms"], 20)
    ws += 10 if r["meta_title"] else 0
    ws += 10 if r["meta_description"] else 0
    ws += 10 if r["has_h1"] else 0
    if r["broken_links"] is None:
        ws += 10
    elif r["broken_links"] == 0:
        ws += 10
    elif r["broken_links"] <= 2:
        ws += 5
    r["website_score"] = _clamp(ws)

    # ---- SEO score ----
    seo = 0
    t = r["meta_title"]
    if t:
        seo += 25 if 10 <= len(t) <= 65 else 15
    d = r["meta_description"]
    if d:
        seo += 25 if 50 <= len(d) <= 165 else 15
    seo += 15 if r["has_h1"] else 0
    seo += 15 if r["https"] else 0
    seo += 10 if r["mobile_friendly"] else 0
    seo += 10 if r["has_lang"] else 0
    r["seo_score"] = _clamp(seo)

    # ---- Modernization score (does it look current?) ----
    mod = 0
    mod += 30 if r["mobile_friendly"] else 0
    mod += 20 if r["https"] else 0
    mod += _speed_points(r["load_ms"], 20)
    mod += 15 if r["html5"] else 0
    if r["img_alt_ratio"] is None:
        mod += 15
    else:
        mod += 15 * r["img_alt_ratio"]
    r["modernization_score"] = _clamp(mod)


def classify_opportunity(has_website: bool, analysis: dict) -> str:
    """High / Medium / Low based on how much work the site needs."""
    if not has_website or not analysis["reachable"]:
        return "High"
    ws = analysis["website_score"]
    seo = analysis["seo_score"]
    if ws < 55 or seo < 45 or not analysis["mobile_friendly"] or not analysis["https"]:
        return "High"
    if ws < 78 or seo < 70:
        return "Medium"
    return "Low"
