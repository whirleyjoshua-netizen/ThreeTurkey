-- ══════════════════════════════════════════
-- EXISTING TABLES
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS waitlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    email               TEXT NOT NULL UNIQUE,
    stripe_customer_id  TEXT,
    stripe_session_id   TEXT,
    amount_paid         INTEGER NOT NULL DEFAULT 14900,
    paid_at             TEXT DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════
-- USERS & AUTH
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT,
    picture_url     TEXT,
    google_id       TEXT UNIQUE,
    access_token    TEXT,
    refresh_token   TEXT,
    token_expires_at TEXT,
    stripe_customer_id TEXT,
    is_lifetime     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    last_login_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);

-- ══════════════════════════════════════════
-- PROPERTIES (GA4 + Search Console sites)
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS properties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ga4_property_id TEXT,
    gsc_site_url    TEXT,
    display_name    TEXT NOT NULL,
    domain          TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════
-- AUDITS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS audits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending',
    pages_scanned   INTEGER DEFAULT 0,
    issues_found    INTEGER DEFAULT 0,
    score           INTEGER,
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    status_code     INTEGER,
    title           TEXT,
    meta_description TEXT,
    h1_count        INTEGER DEFAULT 0,
    h2_count        INTEGER DEFAULT 0,
    word_count      INTEGER DEFAULT 0,
    has_canonical   INTEGER DEFAULT 0,
    has_og_tags     INTEGER DEFAULT 0,
    load_time_ms    INTEGER,
    issues_json     TEXT,
    crawled_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_issues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    page_id         INTEGER REFERENCES audit_pages(id) ON DELETE CASCADE,
    severity        TEXT NOT NULL DEFAULT 'warning',
    category        TEXT NOT NULL,
    message         TEXT NOT NULL,
    suggestion      TEXT,
    url             TEXT
);

-- ══════════════════════════════════════════
-- KEYWORDS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS keywords (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    keyword         TEXT NOT NULL,
    intent          TEXT,
    cluster         TEXT,
    search_volume   INTEGER,
    difficulty      INTEGER,
    current_position REAL,
    previous_position REAL,
    clicks          INTEGER DEFAULT 0,
    impressions     INTEGER DEFAULT 0,
    ctr             REAL,
    url             TEXT,
    fetched_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(property_id, keyword)
);

-- ══════════════════════════════════════════
-- CONTENT GAPS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS content_gaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    competitor_url  TEXT,
    competitor_domain TEXT,
    estimated_volume INTEGER,
    difficulty      INTEGER,
    priority_score  REAL,
    status          TEXT DEFAULT 'open',
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════
-- CONTENT BRIEFS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS briefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    target_keyword  TEXT NOT NULL,
    secondary_keywords TEXT,
    target_word_count INTEGER,
    outline_json    TEXT NOT NULL,
    internal_links  TEXT,
    competitor_urls TEXT,
    status          TEXT DEFAULT 'draft',
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════
-- GA4 SNAPSHOTS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ga4_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    date_range      TEXT NOT NULL,
    metric          TEXT NOT NULL,
    dimension       TEXT,
    data_json       TEXT NOT NULL,
    fetched_at      TEXT DEFAULT (datetime('now'))
);

-- ══════════════════════════════════════════
-- AI INSIGHTS
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS insights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    insight_type    TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    data_json       TEXT,
    dismissed       INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);
