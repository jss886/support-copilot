-- 作用：为用户画像记忆增加唯一约束，避免同一用户下同一类 profile 键重复堆积。
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_memory_profile_unique
ON user_memory(user_id, memory_key, memory_type);

-- 作用：为按用户读取长期记忆补索引，减少 planner 前拼接用户画像时的扫描成本。
CREATE INDEX IF NOT EXISTS idx_user_memory_user_type_updated
ON user_memory(user_id, memory_type, updated_at DESC);

-- 作用：为 task_memory 的向量检索补 ivfflat 索引，提升 planner 前经验检索性能。
CREATE INDEX IF NOT EXISTS idx_task_memory_embedding_ivfflat
ON task_memory
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 作用：为 task_memory 的关键词字段补 GIN 索引，便于后续混合检索和标签过滤。
CREATE INDEX IF NOT EXISTS idx_task_memory_keywords_gin
ON task_memory
USING GIN (keywords);
