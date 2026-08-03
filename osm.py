"""Find local businesses using OpenStreetMap — free and no API key.

Flow:
  1. Nominatim geocodes "City, State, Country" into a bounding box.
  2. Overpass returns businesses of the chosen category inside that box.
  3. OSM tags are mapped into our lead dictionary.

Note: OSM has no Google-style review counts or star ratings, so those
fields are left empty. Everything else (phone, email, website, address,
social links) comes straight from public OSM tags.
"""
import asyncio
import re

import httpx

from .config import (NOMINATIM_URL, OVERPASS_URLS, OVERPASS_TIMEOUT, USER_AGENT)

# Business category -> OpenStreetMap tag selectors.
# Each category may match several tags (unioned in the Overpass query).
CATEGORY_TAGS = {
    "Plumbers":      [("craft", "plumber")],
    "Electricians":  [("craft", "electrician")],
    "Roofing":       [("craft", "roofer")],
    "HVAC":          [("craft", "hvac"), ("craft", "heating_engineer")],
    "Landscapers":   [("craft", "gardener")],
    "Painters":      [("craft", "painter")],
    "Carpenters":    [("craft", "carpenter")],
    "Dentists":      [("amenity", "dentist"), ("healthcare", "dentist")],
    "Doctors":       [("amenity", "doctors"), ("healthcare", "doctor")],
    "Restaurants":   [("amenity", "restaurant")],
    "Cafes":         [("amenity", "cafe")],
    "Bars":          [("amenity", "bar"), ("amenity", "pub")],
    "Hair salons":   [("shop", "hairdresser")],
    "Beauty salons": [("shop", "beauty")],
    "Auto repair":   [("shop", "car_repair")],
    "Car dealers":   [("shop", "car")],
    "Law firms":     [("office", "lawyer")],
    "Accountants":   [("office", "accountant")],
    "Real estate":   [("office", "estate_agent")],
    "Gyms":          [("leisure", "fitness_centre")],
    "Veterinarians": [("amenity", "veterinary")],
    "Florists":      [("shop", "florist")],
    "Bakeries":      [("shop", "bakery")],
}

CATEGORIES = list(CATEGORY_TAGS.keys())

# Special value: scan every category at once.
ALL_CATEGORIES = "All categories"

# Reverse lookup so an "all categories" scan can label each result.
TAG_TO_CATEGORY = {
    (k, v): name for name, sels in CATEGORY_TAGS.items() for k, v in sels
}


def _detect_category(tags: dict) -> str:
    for k, v in TAG_TO_CATEGORY:
        if tags.get(k) == v:
            return TAG_TO_CATEGORY[(k, v)]
    return "Other"

# Common words people type -> one of our known categories above.
SYNONYMS = {
    "plumber": "Plumbers", "plumbing": "Plumbers",
    "electrician": "Electricians", "electrical": "Electricians",
    "roofer": "Roofing", "roofing": "Roofing",
    "heating": "HVAC", "air conditioning": "HVAC", "ac": "HVAC",
    "landscaper": "Landscapers", "landscaping": "Landscapers",
    "lawn care": "Landscapers", "gardener": "Landscapers",
    "painter": "Painters", "painting": "Painters",
    "carpenter": "Carpenters", "carpentry": "Carpenters",
    "dentist": "Dentists", "dental": "Dentists",
    "doctor": "Doctors", "physician": "Doctors", "clinic": "Doctors",
    "restaurant": "Restaurants", "diner": "Restaurants",
    "coffee": "Cafes", "coffee shop": "Cafes", "cafe": "Cafes",
    "bar": "Bars", "pub": "Bars",
    "barber": "Hair salons", "barbershop": "Hair salons",
    "hairdresser": "Hair salons", "hair": "Hair salons", "hair salon": "Hair salons",
    "beauty": "Beauty salons", "nail salon": "Beauty salons", "spa": "Beauty salons",
    "mechanic": "Auto repair", "auto repair": "Auto repair",
    "car repair": "Auto repair", "garage": "Auto repair", "body shop": "Auto repair",
    "car dealer": "Car dealers", "dealership": "Car dealers",
    "lawyer": "Law firms", "attorney": "Law firms", "law firm": "Law firms",
    "accountant": "Accountants", "cpa": "Accountants", "bookkeeper": "Accountants",
    "real estate": "Real estate", "realtor": "Real estate", "estate agent": "Real estate",
    "gym": "Gyms", "fitness": "Gyms",
    "vet": "Veterinarians", "veterinarian": "Veterinarians", "animal hospital": "Veterinarians",
    "florist": "Florists", "flowers": "Florists",
    "bakery": "Bakeries", "baker": "Bakeries",
}

# Keys searched when a typed category doesn't match a known one.
GENERIC_KEYS = ["shop", "craft", "amenity", "office", "healthcare",
                "leisure", "tourism"]


def resolve_selectors(category: str) -> list[tuple[str, str, bool]]:
    """Return a list of (key, value, is_regex) OSM selectors for a category.

    Known categories and synonyms map to exact tags. Anything else becomes a
    fuzzy substring search across common business keys, so users can type
    virtually any business type (e.g. "pharmacy", "tattoo", "butcher").
    """
    if category == ALL_CATEGORIES:
        return [(k, v, False)
                for sels in CATEGORY_TAGS.values() for k, v in sels]

    if category in CATEGORY_TAGS:
        return [(k, v, False) for k, v in CATEGORY_TAGS[category]]

    norm = category.strip().lower()
    mapped = SYNONYMS.get(norm)
    if not mapped:
        for name in CATEGORY_TAGS:
            if name.lower() == norm:
                mapped = name
                break
    if mapped:
        return [(k, v, False) for k, v in CATEGORY_TAGS[mapped]]

    # Free-text fallback: match the word inside any tag value (case-insensitive).
    value = re.sub(r"[^a-z0-9_]", "", norm.replace(" ", "_"))
    if not value:
        return []
    return [(k, value, True) for k in GENERIC_KEYS]


async def geocode(city: str, state: str, country: str,
                  whole_state: bool = False) -> dict | None:
    """Return {'south','north','west','east','lat','lon'} or None.

    When whole_state is True the city is ignored and the bounding box covers
    the entire state/province. Otherwise it tries the full "city, state,
    country" string first, then progressively looser fallbacks so a minor
    mismatch (e.g. wrong country spelling) still resolves.
    """
    if whole_state:
        variants = [
            ", ".join(p for p in (state, country) if p),
            state,
            country,
        ]
    else:
        variants = [
            ", ".join(p for p in (city, state, country) if p),
            ", ".join(p for p in (city, state) if p),
            ", ".join(p for p in (city, country) if p),
            city,
        ]
    headers = {"User-Agent": USER_AGENT}
    seen = set()
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for query in variants:
            if not query or query in seen:
                continue
            seen.add(query)
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": query, "format": "json", "limit": 1},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue
            if data:
                hit = data[0]
                # boundingbox = [south, north, west, east] as strings
                s, n, w, e = (float(x) for x in hit["boundingbox"])
                return {"south": s, "north": n, "west": w, "east": e,
                        "lat": float(hit["lat"]), "lon": float(hit["lon"])}
    return None


def _build_query(bbox: dict, category: str, limit: int = 300) -> str:
    selectors = resolve_selectors(category)
    box = f'{bbox["south"]},{bbox["west"]},{bbox["north"]},{bbox["east"]}'
    parts = []
    for k, v, is_regex in selectors:
        match = f'"{k}"~"{v}",i' if is_regex else f'"{k}"="{v}"'
        parts.append(f'  node[{match}]({box});')
        parts.append(f'  way[{match}]({box});')
    body = "\n".join(parts)
    return f"[out:json][timeout:{int(OVERPASS_TIMEOUT)}];\n(\n{body}\n);\nout center tags {int(limit)};"


def _first(tags: dict, *keys):
    for k in keys:
        if tags.get(k):
            return tags[k]
    return None


def _build_address(tags: dict) -> str:
    parts = []
    hn, st = tags.get("addr:housenumber"), tags.get("addr:street")
    if hn and st:
        parts.append(f"{hn} {st}")
    elif st:
        parts.append(st)
    for k in ("addr:city", "addr:state", "addr:postcode"):
        if tags.get(k):
            parts.append(tags[k])
    return ", ".join(parts)


def _social_url(value: str, base: str) -> str | None:
    """OSM social tags may be a full URL or just a handle/page name."""
    if not value:
        return None
    if value.startswith("http"):
        return value
    return base + value.lstrip("@/")


def _to_lead(element: dict, category: str) -> dict | None:
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None  # unnamed points aren't useful leads

    # For an "all categories" scan, label each lead by its detected type.
    if category == ALL_CATEGORIES:
        category = _detect_category(tags)

    if element["type"] == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:  # way -> Overpass 'center'
        center = element.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")

    gmaps = (f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
             if lat and lon else
             f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}")

    return {
        "name": name,
        "category": category,
        "phone": _first(tags, "phone", "contact:phone"),
        "email": _first(tags, "email", "contact:email"),
        "website": _first(tags, "website", "contact:website"),
        "address": _build_address(tags),
        "city": tags.get("addr:city"),
        "state": tags.get("addr:state"),
        "country": tags.get("addr:country"),
        "lat": lat, "lon": lon, "gmaps_url": gmaps,
        "review_count": None, "rating": None,   # not available from OSM
        "facebook": _social_url(_first(tags, "contact:facebook", "facebook"),
                                "https://facebook.com/"),
        "instagram": _social_url(_first(tags, "contact:instagram", "instagram"),
                                 "https://instagram.com/"),
        "linkedin": _social_url(_first(tags, "contact:linkedin", "linkedin"),
                                "https://linkedin.com/company/"),
        "twitter": _social_url(_first(tags, "contact:twitter", "twitter"),
                               "https://twitter.com/"),
        "owner": tags.get("operator"),
    }


async def _overpass_query(query: str) -> list[dict]:
    """Race the free mirrors two at a time and take the first that answers.

    A single slow/stalled mirror no longer holds up the whole search — we fire
    two requests in parallel and use whichever returns first, cancelling the
    loser.
    """
    headers = {"User-Agent": USER_AGENT}
    timeout = httpx.Timeout(connect=8.0, read=OVERPASS_TIMEOUT, write=15.0, pool=8.0)
    errors = []

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        async def fetch(url: str) -> list[dict]:
            resp = await client.post(url, data={"data": query})
            resp.raise_for_status()
            return resp.json().get("elements", [])

        # Work through the mirrors in pairs; within a pair, first success wins.
        for i in range(0, len(OVERPASS_URLS), 2):
            group = OVERPASS_URLS[i:i + 2]
            pending = {asyncio.create_task(fetch(u)) for u in group}
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED)
                winner = None
                for task in done:
                    try:
                        winner = task.result()
                        break
                    except Exception as exc:
                        errors.append(str(exc))
                if winner is not None:
                    for p in pending:
                        p.cancel()
                    return winner
    raise RuntimeError(f"All Overpass mirrors failed ({'; '.join(errors[-2:])})")


async def find_businesses(bbox: dict, category: str, limit: int = 300) -> list[dict]:
    query = _build_query(bbox, category, limit)
    elements = await _overpass_query(query)

    leads, seen = [], set()
    for el in elements:
        lead = _to_lead(el, category)
        if not lead:
            continue
        key = (lead["name"].lower(), lead.get("phone") or lead.get("address"))
        if key in seen:
            continue
        seen.add(key)
        leads.append(lead)
    return leads
