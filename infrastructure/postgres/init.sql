-- Virtus Job — PostgreSQL Initialization
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS "unaccent";   -- accent-insensitive search

-- Create text search config for Portuguese
CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS portuguese_unaccent (
  COPY = pg_catalog.portuguese
);

ALTER TEXT SEARCH CONFIGURATION portuguese_unaccent
  ALTER MAPPING FOR hword, hword_part, word
  WITH unaccent, portuguese_stem;
