"""Alembic 환경 설정.
이 프로젝트는 SQLAlchemy ORM 모델 없이 raw SQL로 스키마를 정의하므로 autogenerate는 지원하지
않는다 — 스키마 변경은 항상 `alembic revision -m "..."`으로 새 마이그레이션 파일을 만들고
`op.execute()`로 SQL을 직접 작성한다. app/database.py의 DATABASE_URL(SQLite/PostgreSQL 겸용)을
그대로 재사용해 애플리케이션과 항상 동일한 DB를 대상으로 하게 한다.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import DATABASE_URL, engine  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
