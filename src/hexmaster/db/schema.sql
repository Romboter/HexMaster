-- Run once in Postgres
-- run while connected to some existing db (usually "postgres")
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hexmaster') THEN
    CREATE DATABASE hexmaster;
  END IF;
END $$;

-- Global Item Catalog
CREATE TABLE IF NOT EXISTS catalog_items (
  codename         TEXT NOT NULL,
  displayname      TEXT NOT NULL,
  factionvariant   TEXT NOT NULL CHECK (factionvariant IN ('Colonials', 'Wardens', 'Both')),
  quantitypercrate INTEGER NULL,
  PRIMARY KEY (codename, displayname)
);

-- Staging table for catalog imports
CREATE TABLE IF NOT EXISTS catalog_items_stage (
  codename         TEXT NOT NULL,
  displayname      TEXT NOT NULL,
  factionvariant   TEXT NOT NULL,
  quantitypercrate INTEGER NULL
);

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

-- Add foreign key to ensure items in snapshots exist in our catalog
-- Note: This requires catalog data to be present before snapshot ingestion
ALTER TABLE snapshot_items 
  ADD CONSTRAINT fk_snapshot_items_catalog 
  FOREIGN KEY (code_name, item_name) 
  REFERENCES catalog_items (codename, displayname);

CREATE INDEX IF NOT EXISTS idx_snapshots_town_struct_name_time
  ON stockpile_snapshots(town, struct_type, stockpile_name, captured_at DESC);
