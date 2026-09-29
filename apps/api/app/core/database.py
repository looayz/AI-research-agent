import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, event, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes stored as naive UTC.

    asyncpg refuses aware datetimes for ``timestamp without time zone`` columns
    and SQLite drops the offset, so values are normalised to naive UTC on the
    way in and tagged as UTC on the way out. The column type stays a plain
    ``DateTime`` so databases created by earlier versions keep working.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _engine_kwargs() -> dict:
    kwargs: dict = {"echo": settings.DEBUG}
    if settings.is_sqlite:
        # Wait on the write lock instead of failing with "database is locked"
        # when several researches run at once.
        kwargs["connect_args"] = {"timeout": 30}
    else:
        kwargs["pool_pre_ping"] = True
    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs())

if settings.is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        # WAL lets the SSE readers poll while the orchestrator writes.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def _backfill(conn: Connection, added: set[tuple[str, str]]) -> None:
    """One-off data fixes for databases created by the first version."""
    if ("research_events", "seq") in added:
        # Number existing events per research in chronological order.
        conn.exec_driver_sql(
            "UPDATE research_events SET seq = (SELECT COUNT(*) FROM research_events e2 "
            "WHERE e2.research_id = research_events.research_id AND (e2.created_at < research_events.created_at "
            "OR (e2.created_at = research_events.created_at AND e2.id <= research_events.id)))"
        )
    if ("sources", "origin") in added:
        # The first version marked recalled sources by prefixing their title,
        # and the prefix accumulated on every recall.
        conn.exec_driver_sql("UPDATE sources SET origin = 'memory' WHERE title LIKE '[Reused Memory]%'")
        for _ in range(5):
            conn.exec_driver_sql("UPDATE sources SET title = SUBSTR(title, 17) WHERE title LIKE '[Reused Memory] %'")


def _add_missing_columns(conn: Connection) -> None:
    """Additive schema sync for databases created by an older version.

    ``create_all`` never alters existing tables, so columns introduced later
    are added here. Only nullable / defaulted columns are ever added, which
    both SQLite and PostgreSQL support with a plain ``ALTER TABLE``.
    """
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    added: set[tuple[str, str]] = set()
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl_type = column.type.compile(dialect=conn.dialect)
            default = ""
            if column.server_default is not None:
                arg = column.server_default.arg
                if isinstance(arg, str):
                    default = " DEFAULT '" + arg.replace("'", "''") + "'"
                else:
                    default = f" DEFAULT {arg.text}"
            conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}{default}")
            added.add((table.name, column.name))
            logger.info("Added missing column %s.%s", table.name, column.name)
    if added:
        _backfill(conn, added)


async def init_db() -> None:
    # Import models so they are registered on Base.metadata.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
