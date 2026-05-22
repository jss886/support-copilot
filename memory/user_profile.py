import json

from memory.db import _build_db_params
from rag.db import connect_postgres


# 作用：读取某个用户的长期信息，并拼成适合直接注入 prompt 的简短文本。
def load_user_profile_text(user_id: str) -> str:
    if not user_id:
        return ""
    params = _build_db_params()
    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, metadata
                FROM user_memory
                WHERE user_id = %s
                  AND memory_type = 'profile'
                ORDER BY importance_score DESC, updated_at DESC
                LIMIT 20
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    if not rows:
        return ""

    facts: list[str] = []
    preferences: list[str] = []
    for content, metadata in rows:
        if content:
            facts.append(str(content).strip())
        resolved_metadata = json.loads(metadata) if isinstance(metadata, str) else (metadata or {})
        for item in resolved_metadata.get("preferences", []):
            text = str(item).strip()
            if text and text not in preferences:
                preferences.append(text)

    lines: list[str] = []
    if facts:
        lines.append("用户长期信息：")
        lines.extend(f"- {item}" for item in facts[:10])
    if preferences:
        lines.append("用户偏好：")
        lines.extend(f"- {item}" for item in preferences[:10])
    return "\n".join(lines)
