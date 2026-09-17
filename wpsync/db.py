"""MySQL connection and the page query."""

import pymysql
import pymysql.cursors

from wpsync.config import TABLE_PREFIX_RE, DatabaseConfig

# MySQL error codes for "can't connect" — Local.app's mysqld only listens while
# the site is running, so a refused connection almost always just means the
# site is stopped, not a real driver problem worth a raw traceback.
_CONNECTION_REFUSED_ERRNOS = {2003, 2002}


class DatabaseError(Exception):
    """Raised for connection failures and query-time problems."""


def connect(database: DatabaseConfig) -> pymysql.connections.Connection:
    kwargs = dict(
        db=database.name,
        user=database.user,
        password=database.password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    if database.socket:
        kwargs["unix_socket"] = database.socket
    else:
        kwargs["host"] = database.host
        kwargs["port"] = database.port

    try:
        return pymysql.connect(**kwargs)
    except pymysql.err.OperationalError as e:
        errno = e.args[0] if e.args else None
        if errno in _CONNECTION_REFUSED_ERRNOS:
            raise DatabaseError(
                "could not connect to the database — the site is most likely not "
                "running in Local.app. Start it there and try again."
            ) from e
        raise DatabaseError(str(e)) from e


def fetch_pages(conn, table_prefix: str, post_types, post_status) -> list:
    if not TABLE_PREFIX_RE.match(table_prefix):
        raise DatabaseError(
            f"table_prefix '{table_prefix}' contains characters outside "
            "[A-Za-z0-9_] and cannot be safely used in a query"
        )

    sql = (
        f"SELECT ID, post_parent, post_name, post_title, post_status, "
        f"post_modified, post_content "
        f"FROM {table_prefix}posts "
        f"WHERE post_type IN %s AND post_status IN %s"
    )
    with conn.cursor() as cursor:
        cursor.execute(sql, (tuple(post_types), tuple(post_status)))
        return list(cursor.fetchall())
