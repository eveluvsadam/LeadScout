"""Database layer (SQLAlchemy Core).

Works with SQLite (local, default) or PostgreSQL (hosted, via DATABASE_URL).
Same functions as before, so the rest of the app is unchanged.
"""
from pathlib import Path

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text,
                        case, create_engine, delete, func, insert, inspect,
                        select, text, update)

from .config import DATABASE_URL, DB_PATH

if DATABASE_URL.startswith("sqlite"):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
metadata = MetaData()

searches = Table(
    "searches", metadata,
    Column("id", Integer, primary_key=True),
    Column("city", Text), Column("state", Text), Column("country", Text),
    Column("category", Text),
    Column("result_count", Integer, default=0),
    Column("created_at", Text, server_default=text("CURRENT_TIMESTAMP")),
)

leads = Table(
    "leads", metadata,
    Column("id", Integer, primary_key=True),
    Column("search_id", Integer),
    Column("name", Text, nullable=False),
    Column("category", Text),
    Column("phone", Text), Column("email", Text), Column("website", Text),
    Column("address", Text), Column("city", Text), Column("state", Text),
    Column("country", Text), Column("lat", Float), Column("lon", Float),
    Column("gmaps_url", Text),
    Column("review_count", Integer), Column("rating", Float),
    Column("facebook", Text), Column("instagram", Text),
    Column("linkedin", Text), Column("twitter", Text), Column("owner", Text),
    Column("has_website", Integer, default=0),
    Column("https", Integer, default=0),
    Column("mobile_friendly", Integer, default=0),
    Column("meta_title", Text), Column("meta_description", Text),
    Column("load_ms", Integer), Column("broken_links", Integer),
    Column("website_score", Integer), Column("seo_score", Integer),
    Column("modernization_score", Integer),
    Column("opportunity", Text), Column("recommendation", Text),
    Column("emailed_at", Text),
    Column("created_at", Text, server_default=text("CURRENT_TIMESTAMP")),
)

settings = Table(
    "settings", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text),
)

LEAD_COLUMNS = [
    "search_id", "name", "category", "phone", "email", "website", "address",
    "city", "state", "country", "lat", "lon", "gmaps_url", "review_count",
    "rating", "facebook", "instagram", "linkedin", "twitter", "owner",
    "has_website", "https", "mobile_friendly", "meta_title", "meta_description",
    "load_ms", "broken_links", "website_score", "seo_score",
    "modernization_score", "opportunity", "recommendation",
]


def init_db() -> None:
    metadata.create_all(engine)
    # Migration for older SQLite databases created before emailed_at existed.
    cols = [c["name"] for c in inspect(engine).get_columns("leads")]
    if "emailed_at" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE leads ADD COLUMN emailed_at TEXT"))


# --------------------------------------------------------------------------- #
#  Searches                                                                    #
# --------------------------------------------------------------------------- #
def create_search(city, state, country, category) -> int:
    with engine.begin() as conn:
        result = conn.execute(insert(searches).values(
            city=city, state=state, country=country, category=category))
        return result.inserted_primary_key[0]


def set_search_count(search_id: int, count: int) -> None:
    with engine.begin() as conn:
        conn.execute(update(searches).where(searches.c.id == search_id)
                     .values(result_count=count))


def list_searches() -> list:
    with engine.connect() as conn:
        rows = conn.execute(select(searches).order_by(searches.c.id.desc())).mappings()
        return [dict(r) for r in rows]


def delete_search(search_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(delete(leads).where(leads.c.search_id == search_id))
        conn.execute(delete(searches).where(searches.c.id == search_id))


def delete_all_leads() -> None:
    with engine.begin() as conn:
        conn.execute(delete(leads))
        conn.execute(delete(searches))


# --------------------------------------------------------------------------- #
#  Leads                                                                       #
# --------------------------------------------------------------------------- #
def insert_lead(lead: dict) -> None:
    insert_leads([lead])


def insert_leads(lead_list: list[dict]) -> None:
    if not lead_list:
        return
    rows = [{c: lead.get(c) for c in LEAD_COLUMNS} for lead in lead_list]
    with engine.begin() as conn:
        conn.execute(insert(leads), rows)


def get_lead(lead_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(select(leads).where(leads.c.id == lead_id)).mappings().first()
        return dict(row) if row else None


def get_leads_by_ids(ids: list[int]) -> list:
    if not ids:
        return []
    with engine.connect() as conn:
        rows = conn.execute(select(leads).where(leads.c.id.in_(ids))).mappings()
        return [dict(r) for r in rows]


def mark_emailed(lead_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(update(leads).where(leads.c.id == lead_id)
                     .values(emailed_at=func.current_timestamp()))


def query_leads(opportunity=None, has_website=None, category=None,
                search_id=None, callable_only=False, has_email=None,
                emailed_only=False, limit=1000) -> list:
    q = select(leads)
    if opportunity:
        q = q.where(leads.c.opportunity == opportunity)
    if has_website is not None:
        q = q.where(leads.c.has_website == (1 if has_website else 0))
    if category:
        q = q.where(leads.c.category == category)
    if search_id:
        q = q.where(leads.c.search_id == search_id)
    if callable_only:
        q = q.where(((leads.c.phone.isnot(None)) & (leads.c.phone != "")) |
                    ((leads.c.email.isnot(None)) & (leads.c.email != "")))
    if has_email:
        q = q.where((leads.c.email.isnot(None)) & (leads.c.email != ""))
    if emailed_only:
        q = q.where(leads.c.emailed_at.isnot(None))
    opp_order = case((leads.c.opportunity == "High", 0),
                     (leads.c.opportunity == "Medium", 1), else_=2)
    q = q.order_by(opp_order, leads.c.id.desc()).limit(limit)
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(q).mappings()]


def _sum_case(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def stats() -> dict:
    has_email = (leads.c.email.isnot(None)) & (leads.c.email != "")
    has_phone = (leads.c.phone.isnot(None)) & (leads.c.phone != "")
    q = select(
        func.count().label("total"),
        _sum_case(leads.c.has_website == 0).label("no_website"),
        _sum_case(leads.c.opportunity == "High").label("high_opp"),
        _sum_case((leads.c.has_website == 1) & (leads.c.website_score < 60)).label("outdated"),
        _sum_case(has_phone | has_email).label("callable"),
        _sum_case(has_email).label("emailable"),
        _sum_case(leads.c.emailed_at.isnot(None)).label("emailed"),
        func.avg(case((leads.c.has_website == 1, leads.c.website_score))).label("avg_website"),
        func.avg(case((leads.c.has_website == 1, leads.c.seo_score))).label("avg_seo"),
    )
    with engine.connect() as conn:
        d = dict(conn.execute(q).mappings().first())
    for k in ("total", "no_website", "high_opp", "outdated", "callable",
              "emailable", "emailed"):
        d[k] = d[k] or 0
    d["avg_website"] = round(d["avg_website"], 1) if d["avg_website"] is not None else None
    d["avg_seo"] = round(d["avg_seo"], 1) if d["avg_seo"] is not None else None
    return d


# --------------------------------------------------------------------------- #
#  Settings (key/value, e.g. editable package prices)                          #
# --------------------------------------------------------------------------- #
def get_setting(key: str, default=None):
    with engine.connect() as conn:
        row = conn.execute(select(settings.c.value)
                           .where(settings.c.key == key)).first()
        return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with engine.begin() as conn:
        exists = conn.execute(select(settings.c.key)
                              .where(settings.c.key == key)).first()
        if exists:
            conn.execute(update(settings).where(settings.c.key == key)
                         .values(value=value))
        else:
            conn.execute(insert(settings).values(key=key, value=value))


def reset_admin() -> None:
    """Forget the admin password (and any session) so /admin shows setup again."""
    with engine.begin() as conn:
        conn.execute(delete(settings).where(settings.c.key.in_(
            ["admin_pw_hash", "admin_pw_salt", "admin_session"])))
