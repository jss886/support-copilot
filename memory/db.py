import json

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url


# 作用：统一获取数据库连接参数，避免 memory 模块重复写解析逻辑。
def _build_db_params():
    jdbc_url = settings.postgres.jdbc_url
    db_user = settings.postgres.user
    db_password = settings.postgres.password
    if not jdbc_url or not db_user or not db_password:
        raise ValueError("Missing PostgreSQL config for memory module.")
    return parse_jdbc_postgres_url(
        jdbc_url,
        user=db_user,
        password=db_password,
        connect_timeout=settings.postgres.connect_timeout,
    )


# 作用：读取指定 session 的 state JSON，供短期记忆持久化和恢复使用。
def load_session_state(session_id: str) -> dict:
    if not session_id:
        return {}
    params = _build_db_params()
    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
    if not row or row[0] is None:
        return {}
    state = row[0]
    if isinstance(state, str):
        return json.loads(state)
    return state


# 作用：upsert 会话状态，把短期记忆和最后一次问答摘要落到 sessions 表。
def save_session_state(
    *,
    session_id: str,
    user_id: str,
    state: dict,
    current_topic: str = "",
    last_user_query: str = "",
    last_answer_summary: str = "",
) -> None:
    if not session_id:
        return
    params = _build_db_params()
    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    user_id,
                    current_topic,
                    last_user_query,
                    last_answer_summary,
                    state
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    current_topic = EXCLUDED.current_topic,
                    last_user_query = EXCLUDED.last_user_query,
                    last_answer_summary = EXCLUDED.last_answer_summary,
                    state = EXCLUDED.state,
                    updated_at = NOW()
                """,
                (
                    session_id,
                    user_id,
                    current_topic or None,
                    last_user_query or None,
                    last_answer_summary or None,
                    json.dumps(state, ensure_ascii=False),
                ),
            )
        conn.commit()
