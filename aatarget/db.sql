CREATE TABLE kb_documents (
    id UUID PRIMARY KEY,
    doc_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT,
    content_hash VARCHAR(64),
    repo_name TEXT,
    module_name TEXT,
    author TEXT,
    version TEXT,
    tags JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_kb_documents_source_unique
ON kb_documents(source) WHERE source IS NOT NULL;

CREATE TABLE kb_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    content_summary TEXT,
    token_count INT,
    keywords TEXT[],
    tsv tsvector,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_memory (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    importance_score FLOAT DEFAULT 0.5,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE task_memory (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    task_type TEXT NOT NULL,
    title TEXT,
    problem TEXT NOT NULL,
    resolution TEXT NOT NULL,
    takeaway TEXT,
    embedding vector(1536),
    keywords TEXT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    current_topic TEXT,
    current_module TEXT,
    last_user_query TEXT,
    last_answer_summary TEXT,
    state JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE incident_cases (
    id UUID PRIMARY KEY,
    case_no TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    system_name TEXT,
    module_name TEXT,
    problem_desc TEXT NOT NULL,
    root_cause TEXT,
    resolution TEXT,
    severity TEXT,
    status TEXT,
    keywords TEXT[],
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE api_specs (
    id UUID PRIMARY KEY,
    service_name TEXT NOT NULL,
    module_name TEXT,
    api_name TEXT NOT NULL,
    path TEXT NOT NULL,
    method TEXT NOT NULL,
    request_schema JSONB,
    response_schema JSONB,
    error_codes JSONB,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE module_dependencies (
    id UUID PRIMARY KEY,
    repo_name TEXT NOT NULL,
    module_name TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    dependency_type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 作用：为已有 kb_chunks 数据回填全文检索字段，避免历史数据无法参与关键词召回。
UPDATE kb_chunks
SET tsv = to_tsvector('simple', COALESCE(content, ''))
WHERE tsv IS NULL;

-- 作用：为全文检索字段补充 GIN 索引，提升关键词召回性能。
CREATE INDEX IF NOT EXISTS idx_kb_chunks_tsv
ON kb_chunks
USING GIN (tsv);


