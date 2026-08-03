"""SQLite helpers. Uses only the Python standard library (no ORM)."""
import os
import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"


def get_conn() -> sqlite3.Connection:
    """Return a connection with row access by column name and FK enforcement."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables from schema.sql if they don't already exist."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_FILE.read_text())


def create_search(city, state, country, category) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO searches (city, state, country, category) VALUES (?,?,?,?)",
            (city, state, country, category),
        )
        return cur.lastrowid


def set_search_count(search_id: int, count: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE searches SET result_count=? WHERE id=?", (count, search_id))


LEAD_COLUMNS = [
    "search_id", "name", "category", "phone", "email", "website", "address",
    "city", "state", "country", "lat", "lon", "gmaps_url", "review_count",
    "rating", "facebook", "instagram", "linkedin", "twitter", "owner",
    "has_website", "https", "mobile_friendly", "meta_title", "meta_description",
    "load_ms", "broken_links", "website_score", "seo_score",
    "modernization_score", "opportunity", "recommendation",
]


def insert_lead(lead: dict) -> None:
    insert_leads([lead])


def insert_leads(leads: list[dict]) -> None:
    """Insert many leads in a single transaction (much faster than one-by-one)."""
    if not leads:
        return
    cols = ", ".join(LEAD_COLUMNS)
    placeholders = ", ".join("?" for _ in LEAD_COLUMNS)
    rows = [[lead.get(c) for c in LEAD_COLUMNS] for lead in leads]
    with get_conn() as conn:
        conn.executemany(f"INSERT INTO leads ({cols}) VALUES ({placeholders})", rows)


def get_lead(lead_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None


def query_leads(opportunity=None, has_website=None, category=None,
                search_id=None, limit=1000) -> list:
    sql = "SELECT * FROM leads WHERE 1=1"
    params = []
    if opportunity:
        sql += " AND opportunity = ?"
        params.append(opportunity)
    if has_website is not None:
        sql += " AND has_website = ?"
        params.append(1 if has_website else 0)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if search_id:
        sql += " AND search_id = ?"
        params.append(search_id)
    sql += " ORDER BY CASE opportunity WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def stats() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                                            AS total,
                SUM(CASE WHEN has_website = 0 THEN 1 ELSE 0 END)    AS no_website,
                SUM(CASE WHEN opportunity = 'High' THEN 1 ELSE 0 END) AS high_opp,
                SUM(CASE WHEN has_website = 1 AND website_score < 60 THEN 1 ELSE 0 END) AS outdated,
                AVG(CASE WHEN has_website = 1 THEN website_score END) AS avg_website,
                AVG(CASE WHEN has_website = 1 THEN seo_score END)     AS avg_seo
            FROM leads
            """
        ).fetchone()
    d = dict(row)
    for k in ("total", "no_website", "high_opp", "outdated"):
        d[k] = d[k] or 0
    d["avg_website"] = round(d["avg_website"], 1) if d["avg_website"] is not None else None
    d["avg_seo"] = round(d["avg_seo"], 1) if d["avg_seo"] is not None else None
    return d
