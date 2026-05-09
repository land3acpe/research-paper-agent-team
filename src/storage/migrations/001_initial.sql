-- 001_initial.sql -- MVP1 tables

CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT,
    title_hash TEXT,
    source TEXT NOT NULL,
    source_id TEXT,
    url TEXT,
    pdf_url TEXT,
    authors_json TEXT,
    venue TEXT,
    published_date TEXT,
    indexed_date TEXT,
    abstract TEXT,
    keywords_json TEXT,
    status TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_title_hash ON papers(title_hash);
CREATE INDEX IF NOT EXISTS idx_papers_source_id ON papers(source, source_id);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    profile_slug TEXT NOT NULL,
    schedule_mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    sources_json TEXT,
    query_window_from TEXT,
    query_window_to TEXT,
    raw_count INTEGER DEFAULT 0,
    normalized_count INTEGER DEFAULT 0,
    deduped_count INTEGER DEFAULT 0,
    filtered_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    report_path TEXT,
    log_path TEXT,
    dry_run INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filter_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    paper_id INTEGER,
    decision TEXT NOT NULL,
    reason_code TEXT,
    reason_text TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_filter_decisions_run ON filter_decisions(run_id);

CREATE TABLE IF NOT EXISTS dedup_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id_a INTEGER NOT NULL,
    paper_id_b INTEGER NOT NULL,
    match_type TEXT NOT NULL,
    similarity REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dedup_status ON dedup_candidates(status);
