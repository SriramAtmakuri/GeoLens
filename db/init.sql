CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TYPE job_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE ingestion_jobs (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status           job_status NOT NULL DEFAULT 'pending',
    filename         TEXT NOT NULL,
    total_chunks     INT,
    processed_chunks INT DEFAULT 0,
    error_message    TEXT,
    started_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

CREATE TABLE document_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    geom        GEOMETRY(Point, 4326),
    metadata    JSONB DEFAULT '{}',
    tsv         TSVECTOR,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbour on cosine distance
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIST spatial index
CREATE INDEX ON document_chunks USING gist (geom);

-- GIN full-text index
CREATE INDEX ON document_chunks USING gin (tsv);

-- Auto-update tsvector on insert/update
CREATE OR REPLACE FUNCTION update_tsv() RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv := to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsv_update
    BEFORE INSERT OR UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_tsv();

CREATE TABLE eval_queries (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question            TEXT NOT NULL,
    polygon_geojson     JSONB NOT NULL,
    expected_chunk_ids  UUID[] NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
