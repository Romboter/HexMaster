-- Run once in Postgres
-- run while connected to some existing db (usually "postgres")
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hexmaster') THEN
    CREATE DATABASE hexmaster;
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS stockpile_snapshots (
  id           BIGSERIAL PRIMARY KEY,
  stockpile_key TEXT NOT NULL,          -- e.g. "TheManacle|Seaport|Public"
  captured_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS snapshot_items (
  snapshot_id  BIGINT NOT NULL REFERENCES stockpile_snapshots(id) ON DELETE CASCADE,
  code_name    TEXT NOT NULL,            -- stable item key (best for joins)
  item_name    TEXT NOT NULL,
  quantity     INTEGER,
  is_crated    BOOLEAN,
  per_crate    INTEGER,
  total        INTEGER,
  description  TEXT,
  PRIMARY KEY (snapshot_id, code_name)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_key_time
  ON stockpile_snapshots(stockpile_key, captured_at DESC);
