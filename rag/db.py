from dataclasses import dataclass
from urllib.parse import urlparse

import psycopg
from psycopg import OperationalError


@dataclass
class PostgresConnectionParams:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    connect_timeout: int = 5


# 作用：把 JDBC 风格的 PostgreSQL 地址解析成 psycopg 可直接使用的连接参数。
def parse_jdbc_postgres_url(
    jdbc_url: str,
    user: str,
    password: str,
    connect_timeout: int = 5,
) -> PostgresConnectionParams:
    prefix = "jdbc:"
    normalized = jdbc_url[len(prefix) :] if jdbc_url.startswith(prefix) else jdbc_url
    parsed = urlparse(normalized)
    if parsed.scheme != "postgresql":
        raise ValueError(f"Unsupported JDBC scheme: {parsed.scheme}")
    if not parsed.hostname or not parsed.path:
        raise ValueError(f"Invalid JDBC URL: {jdbc_url}")

    return PostgresConnectionParams(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"),
        user=user,
        password=password,
        connect_timeout=connect_timeout,
    )


# 作用：建立 PostgreSQL 连接，并在数据库不可用时尽快返回明确错误，避免接口长时间卡住。
def connect_postgres(params: PostgresConnectionParams) -> psycopg.Connection:
    try:
        return psycopg.connect(
            host=params.host,
            port=params.port,
            dbname=params.dbname,
            user=params.user,
            password=params.password,
            connect_timeout=params.connect_timeout,
        )
    except OperationalError as exc:
        raise ConnectionError(
            "PostgreSQL 连接失败，请确认数据库已启动且连接配置正确。"
            f" host={params.host} port={params.port} db={params.dbname} "
            f"timeout={params.connect_timeout}s"
        ) from exc
