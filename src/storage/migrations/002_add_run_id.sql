-- 002_add_run_id.sql -- Add run_id to papers for per-run reporting

ALTER TABLE papers ADD COLUMN run_id TEXT;
CREATE INDEX IF NOT EXISTS idx_papers_run_id ON papers(run_id);
