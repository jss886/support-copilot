-- 1. 添加 content_hash 列（SHA256 十六进制，64 字符）
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

-- 2. 给 source 加唯一约束（NULL 之间允许重复，符合 PostgreSQL 语义）
--    如果存在重复行，先保留最新的一条
DELETE FROM kb_documents a
USING kb_documents b
WHERE a.source = b.source
  AND a.source IS NOT NULL
  AND a.created_at < b.created_at;

CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_documents_source_unique
ON kb_documents(source) WHERE source IS NOT NULL;
