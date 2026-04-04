from dataclasses import dataclass
from urllib.parse import urlparse

import psycopg


@dataclass
class PostgresConnectionParams:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def parse_jdbc_postgres_url(jdbc_url: str, user: str, password: str) -> PostgresConnectionParams:
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
    )


def connect_postgres(params: PostgresConnectionParams) -> psycopg.Connection:
    return psycopg.connect(
        host=params.host,
        port=params.port,
        dbname=params.dbname,
        user=params.user,
        password=params.password,
    )
