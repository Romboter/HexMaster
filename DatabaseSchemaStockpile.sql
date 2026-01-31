-- Run once in Postgres
-- run while connected to some existing db (usually "postgres")
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hexmaster') THEN
    CREATE DATABASE hexmaster;
  END IF;
END $$;
DROP TABLE IF EXISTS snapshot_items;
DROP TABLE IF EXISTS stockpile_snapshots;

CREATE TABLE IF NOT EXISTS stockpile_snapshots (
  id             BIGSERIAL PRIMARY KEY,
  town           TEXT NOT NULL,
  struct_type    TEXT NOT NULL,
  stockpile_name TEXT NOT NULL DEFAULT 'Public',
  captured_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE snapshot_items (
  snapshot_id  BIGINT NOT NULL REFERENCES stockpile_snapshots(id) ON DELETE CASCADE,
  code_name    TEXT NOT NULL,            -- stable item key (best for joins)
  item_name    TEXT NOT NULL,
  quantity     INTEGER,
  is_crated    BOOLEAN NOT NULL DEFAULT FALSE,
  per_crate    INTEGER,
  total        INTEGER,
  description  TEXT,
  PRIMARY KEY (snapshot_id, code_name, is_crated)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_town_struct_name_time
  ON stockpile_snapshots(town, struct_type, stockpile_name, captured_at DESC);
