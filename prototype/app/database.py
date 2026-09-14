import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SQLITE_PATH = BASE_DIR / "erp.db"

# prototype/.env 를 자동 로드 (DATABASE_URL, JWT_SECRET 등). 이미 export된 값은 덮어쓰지 않음.
load_dotenv(PROJECT_DIR / ".env", override=False)


def _normalize_database_url(url: str) -> str:
    """Neon/Postgres 연결 문자열을 SQLAlchemy + psycopg2 형식으로 맞춘다."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    # psycopg2는 channel_binding을 안정적으로 지원하지 않음 — Neon은 sslmode=require면 충분
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "channel_binding"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


_raw_url = os.environ.get("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")
DATABASE_URL = _normalize_database_url(_raw_url)

_engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
}
# Neon 등 원격 Postgres: 연결 타임아웃으로 무한 대기를 방지
if DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["connect_args"] = {"connect_timeout": 15}
    # PgBouncer(pooler) transaction 모드와 충돌을 줄이기 위해 풀 단순화
    if "-pooler." in DATABASE_URL:
        from sqlalchemy.pool import NullPool

        _engine_kwargs["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
IS_SQLITE = engine.dialect.name == "sqlite"


def get_conn():
    """SQLAlchemy Connection 반환. 호출부에서 명시적으로 conn.commit()해야 반영된다."""
    conn = engine.connect()
    if IS_SQLITE:
        conn.execute(text("PRAGMA foreign_keys = ON"))
    return conn


def run(conn, sql, params=()):
    """기존 sqlite3 스타일 '?' 포지셔널 플레이스홀더 SQL을, SQLAlchemy text()의 named
    parameter로 자동 변환해 실행한다. main.py의 SQL 문자열을 그대로 재사용하기 위한 어댑터."""
    named_sql = sql
    param_dict = {}
    for i, value in enumerate(params):
        key = f"p{i}"
        named_sql = named_sql.replace("?", f":{key}", 1)
        param_dict[key] = value
    return conn.execute(text(named_sql), param_dict)


def insert_returning(conn, insert_sql, params, pk_col):
    """INSERT문 뒤에 RETURNING을 붙여 새로 생성된 PK를 반환한다.
    SQLite(3.35+)와 PostgreSQL 모두 RETURNING을 지원해 방언에 무관하게 동작한다."""
    sql = insert_sql.rstrip().rstrip(";") + f" RETURNING {pk_col}"
    row = run(conn, sql, params).mappings().fetchone()
    return row[pk_col]


def one(result):
    """Result에서 첫 행을 dict 또는 None으로 반환."""
    row = result.mappings().fetchone()
    return dict(row) if row is not None else None


def rows_to_list(result):
    return [dict(r) for r in result.mappings().fetchall()]


def _split_statements(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]


def _alembic_config():
    """migrations/ 아래 마이그레이션을 이 프로세스의 DATABASE_URL로 실행하기 위한 Config.
    alembic.ini의 sqlalchemy.url을 애플리케이션과 동일한 값으로 덮어써 이중관리를 피한다."""
    from alembic.config import Config

    project_dir = BASE_DIR.parent
    cfg = Config(str(project_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def init_db(reset: bool = False):
    """Alembic 마이그레이션으로 스키마를 최신 상태(head)로 맞춘다(v4, task-plan-mvp-infra.md 참고).
    - 완전 신규 DB(테이블 없음): `alembic upgrade head` — 마이그레이션을 순서대로 적용해 처음부터 구성.
    - 이번 전환 이전에 만들어진 기존 DB(테이블은 있으나 alembic_version 없음): 데이터 손실 없이
      `alembic stamp head`로 "이미 head"라고 표시만 한다(head=현재 스키마와 동일하므로 안전).
    - 이미 alembic으로 추적 중인 DB: `alembic upgrade head`로 신규 마이그레이션만 적용.
    반환값 is_new는 main.py가 시드 실행 여부를 판단하는 데 그대로 사용한다(인터페이스 변경 없음)."""
    if reset and IS_SQLITE and SQLITE_PATH.exists():
        SQLITE_PATH.unlink()

    from alembic import command
    from alembic.script import ScriptDirectory

    insp = inspect(engine)
    is_new = not insp.has_table("company")
    has_alembic_version = insp.has_table("alembic_version")
    cfg = _alembic_config()

    # 이미 head면 upgrade를 건너뛴다 — Neon 등에서 alembic advisory lock 대기를 피하기 위함
    if has_alembic_version and not is_new:
        head = ScriptDirectory.from_config(cfg).get_current_head()
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current == head:
            return False

    if is_new:
        command.upgrade(cfg, "head")
    elif not has_alembic_version:
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
    return is_new
