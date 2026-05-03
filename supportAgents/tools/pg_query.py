import re
from typing import Any

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url

# 只允许这些 SQL 类型（全部只读），其余一律拒绝。
_ALLOWED_PREFIXES = ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE")


def _is_read_only(sql: str) -> bool:
    """检查 SQL 是否为只读语句，拦截写操作和多语句注入。"""
    stripped = sql.strip()
    if not stripped:
        return False
    # 允许尾部有一个分号，但拦截多语句注入（中间含分号）。
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    if ";" in stripped:
        return False
    # 取第一个非空单词，忽略前导括号（含 CTE 的 WITH 可能带括号）
    first_word = stripped.lstrip("(").strip().split(maxsplit=1)[0].upper()
    return first_word in _ALLOWED_PREFIXES


def run_pg_query(sql: str) -> dict[str, Any]:
    """执行一条只读 SQL 查询，返回 {columns: [...], rows: [[...], ...], row_count: N}。

    只允许 SELECT / WITH / EXPLAIN / SHOW / DESCRIBE，其余操作一律拒绝。
    """
    if not _is_read_only(sql):
        return {
            "error": "仅允许只读查询 (SELECT / WITH / EXPLAIN / SHOW / DESCRIBE)，且不支持多语句。",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    pg = settings.postgres
    if not pg.jdbc_url or not pg.user:
        return {
            "error": "PostgreSQL 连接配置不完整，请检查 postgres.jdbc_url 和 postgres.user。",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    try:
        params = parse_jdbc_postgres_url(
            pg.jdbc_url, pg.user, pg.password or "", connect_timeout=pg.connect_timeout
        )
        conn = connect_postgres(params)
    except Exception as exc:
        return {
            "error": f"PostgreSQL 连接失败: {exc}",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        # 对于 EXPLAIN/SHOW 这类不返回标准结果集的语句，直接读文本。
        if cursor.description is None:
            result_text = "\n".join(
                row[0] for row in cursor.fetchall() if row
            )
            return {
                "columns": ["result"],
                "rows": [[result_text]] if result_text else [],
                "row_count": 1 if result_text else 0,
            }

        columns = [desc[0] for desc in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    except Exception as exc:
        return {
            "error": f"查询执行失败: {exc}",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass
