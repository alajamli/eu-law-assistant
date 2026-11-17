-- eu-law-assistant schema (Week 0)
-- Applied automatically by the postgres image on first start.
-- Re-apply by hand with: docker compose exec -T db psql -U postgres -d eulaw < db/init/01_schema.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- Corpus
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    slug        TEXT        NOT NULL,                    -- ai-act | gdpr | data-act
    celex       TEXT,                                    -- e.g. 32024R1689
    title       TEXT        NOT NULL,
    lang        CHAR(2)     NOT NULL CHECK (lang IN ('en', 'fr')),
    source_url  TEXT        NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT,                                    -- sha256 of the cached raw file
    UNIQUE (slug, lang)
);

CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          BIGINT      NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    lang            CHAR(2)     NOT NULL CHECK (lang IN ('en', 'fr')),

    -- Legal structure. NULL where the level does not exist.
    chapter         TEXT,        -- "Chapter III"
    section         TEXT,
    article         TEXT,        -- "5" for Article 5, "R12" for Recital 12
    paragraph       TEXT,        -- "1", "1(a)", NULL
    is_recital      BOOLEAN     NOT NULL DEFAULT false,
    heading_path    TEXT        NOT NULL,                -- "AI Act > Chapter II > Article 5"

    content         TEXT        NOT NULL,                -- breadcrumb-prefixed chunk text
    n_chars         INTEGER     NOT NULL,

    embedding       VECTOR(1024),
    embedding_model TEXT,
    tsv             TSVECTOR,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Makes ingestion idempotent and re-runnable. NULLS NOT DISTINCT (PG15+)
    -- is required because recitals have no paragraph number.
    UNIQUE NULLS NOT DISTINCT (doc_id, article, paragraph, lang, heading_path)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx      ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_doc_article_idx ON chunks (doc_id, article);
CREATE INDEX IF NOT EXISTS chunks_lang_idx     ON chunks (lang);

-- Language-aware full-text vector: a plain generated column cannot vary the
-- text-search config per row, so fill tsv from a trigger instead.
CREATE OR REPLACE FUNCTION chunks_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector(
        CASE NEW.lang WHEN 'fr' THEN 'french'::regconfig ELSE 'english'::regconfig END,
        coalesce(NEW.content, '')
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chunks_tsv_trigger ON chunks;
CREATE TRIGGER chunks_tsv_trigger
    BEFORE INSERT OR UPDATE OF content, lang ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update();

-- ---------------------------------------------------------------------------
-- Chat history (Week 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lang       CHAR(2) NOT NULL DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id            BIGSERIAL PRIMARY KEY,
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content       TEXT NOT NULL,
    citations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    refused       BOOLEAN NOT NULL DEFAULT false,
    latency_ms    INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_session_idx ON messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id         BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating     SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    comment    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Caches: repeated eval questions and repeated user questions must not
-- re-spend LLM quota (Groq free tier is the binding constraint).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key  TEXT PRIMARY KEY,          -- sha256(model | prompt | params)
    response   JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    cache_key  TEXT PRIMARY KEY,          -- sha256(model | text)
    embedding  VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
