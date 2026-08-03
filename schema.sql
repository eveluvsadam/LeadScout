-- LeadScout database schema (SQLite)
-- Two tables: one row per search run, one row per business lead found.

CREATE TABLE IF NOT EXISTS searches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    city          TEXT,
    state         TEXT,
    country       TEXT,
    category      TEXT,
    result_count  INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id           INTEGER REFERENCES searches(id) ON DELETE CASCADE,

    -- Identity / contact (from OpenStreetMap, public data)
    name                TEXT NOT NULL,
    category            TEXT,
    phone               TEXT,
    email               TEXT,
    website             TEXT,
    address             TEXT,
    city                TEXT,
    state               TEXT,
    country             TEXT,
    lat                 REAL,
    lon                 REAL,
    gmaps_url           TEXT,

    -- Not available from free/open data; kept for completeness / future providers
    review_count        INTEGER,
    rating              REAL,

    -- Social profiles (from OSM contact:* tags)
    facebook            TEXT,
    instagram           TEXT,
    linkedin            TEXT,
    twitter             TEXT,
    owner               TEXT,

    -- Website analysis
    has_website         INTEGER DEFAULT 0,   -- 0/1
    https               INTEGER DEFAULT 0,   -- 0/1
    mobile_friendly     INTEGER DEFAULT 0,   -- 0/1
    meta_title          TEXT,
    meta_description    TEXT,
    load_ms             INTEGER,
    broken_links        INTEGER,

    website_score       INTEGER,             -- 0-100
    seo_score           INTEGER,             -- 0-100
    modernization_score INTEGER,             -- 0-100

    opportunity         TEXT,                -- High / Medium / Low
    recommendation      TEXT,

    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_leads_search      ON leads(search_id);
CREATE INDEX IF NOT EXISTS idx_leads_opportunity ON leads(opportunity);
CREATE INDEX IF NOT EXISTS idx_leads_category    ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_haswebsite  ON leads(has_website);
