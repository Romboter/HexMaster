-- Migration to add war_number to stockpile_snapshots
ALTER TABLE stockpile_snapshots ADD COLUMN IF NOT EXISTS war_number INTEGER;
