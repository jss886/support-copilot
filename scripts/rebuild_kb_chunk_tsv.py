import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url
from rag.text_search import build_chunk_search_text, extract_search_keywords, parse_tags


# 作用：解析脚本参数，支持按批次重建 tsv，避免一次性更新过多数据。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="重建 kb_chunks 的中文分词 tsv。")
    parser.add_argument(
        "--jdbc-url",
        default=settings.postgres.jdbc_url,
        help="PostgreSQL JDBC 连接串。",
    )
    parser.add_argument(
        "--db-user",
        default=settings.postgres.user,
        help="PostgreSQL 用户名。",
    )
    parser.add_argument(
        "--db-password",
        default=settings.postgres.password,
        help="PostgreSQL 密码。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每批更新的 chunk 数量。",
    )
    return parser.parse_args()


# 作用：统一解析数据库连接参数，避免脚本在配置缺失时静默失败。
def _resolve_db_config(
    jdbc_url: str | None,
    db_user: str | None,
    db_password: str | None,
) -> tuple[str, str, str, int]:
    resolved_jdbc_url = jdbc_url or settings.postgres.jdbc_url
    resolved_db_user = db_user or settings.postgres.user
    resolved_db_password = db_password or settings.postgres.password
    if not resolved_jdbc_url or not resolved_db_user or not resolved_db_password:
        raise ValueError(
            "Missing PostgreSQL config. Set jdbc_url/db_user/db_password via CLI, "
            "config_local.py, config.py, or environment variables."
        )
    return (
        resolved_jdbc_url,
        resolved_db_user,
        resolved_db_password,
        settings.postgres.connect_timeout,
    )


# 作用：把数据库里的 metadata 统一解析成字典，便于重建检索文本。
def _normalize_metadata(metadata: dict | str | None) -> dict:
    if metadata is None:
        return {}
    if isinstance(metadata, str):
        return json.loads(metadata)
    return metadata


# 作用：按当前中文分词规则全量重建 kb_chunks.tsv，并把标题、来源和标签并入检索文本。
def main() -> None:
    args = parse_args()
    jdbc_url, db_user, db_password, connect_timeout = _resolve_db_config(
        args.jdbc_url,
        args.db_user,
        args.db_password,
    )
    params = parse_jdbc_postgres_url(
        jdbc_url,
        user=db_user,
        password=db_password,
        connect_timeout=connect_timeout,
    )

    select_sql = """
        SELECT
            c.id,
            c.content,
            c.keywords,
            c.metadata,
            d.title,
            d.doc_name,
            d.source,
            d.tags
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id
        ORDER BY c.created_at ASC
        LIMIT %s OFFSET %s
    """
    update_sql = """
        UPDATE kb_chunks
        SET keywords = %s,
            tsv = to_tsvector(%s, %s)
        WHERE id = %s
    """

    total_updated = 0
    offset = 0
    with connect_postgres(params) as conn:
        while True:
            with conn.cursor() as cur:
                cur.execute(select_sql, (args.batch_size, offset))
                rows = cur.fetchall()
            if not rows:
                break

            with conn.cursor() as cur:
                for chunk_id, content, keywords, metadata, title, doc_name, source, tags in rows:
                    resolved_metadata = _normalize_metadata(metadata)
                    resolved_tags = parse_tags(tags)
                    segmented_search_text = build_chunk_search_text(
                        title=title or doc_name or "",
                        source=source or resolved_metadata.get("source", ""),
                        content=content,
                        keywords=keywords or [],
                        tags=resolved_tags,
                        metadata=resolved_metadata,
                    )
                    cur.execute(
                        update_sql,
                        (
                            extract_search_keywords(segmented_search_text),
                            settings.postgres.text_search_config,
                            segmented_search_text,
                            chunk_id,
                        ),
                    )
            conn.commit()
            total_updated += len(rows)
            offset += args.batch_size
            print(f"已更新 {total_updated} 条 kb_chunks.tsv")

    print(f"重建完成，共更新 {total_updated} 条 kb_chunks.tsv。")


if __name__ == "__main__":
    main()
