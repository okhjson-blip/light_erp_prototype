"""app_user에 is_active 플래그 추가 (SSO 리뷰 P1-5)

All-in-One SSO 도입 후 ERP는 Keycloak에서 검증된 이메일을 기존 app_user와 대조해 도메인 세션을
발급한다. 그런데 app_user에는 활성 여부 컬럼이 없어 퇴사자/정지 계정을 차단할 방법이 행 삭제밖에
없었다. R&D는 이미 `isActive`로 같은 판정을 하고 있어 두 시스템의 deprovisioning 정책도 어긋났다.

- is_active: 1이면 로그인 가능. 0이면 password 로그인과 SSO 교환 모두 거부한다.
- 기존 행은 전부 1로 백필한다(기존 동작 유지).

주의: schema_sqlite.sql / schema_postgres.sql은 수정하지 않는다 — 0001이 이 파일들을 실행 시점에
동적으로 읽으므로 스키마 파일을 고치면 신규 설치 시 중복 컬럼 오류가 난다(0003과 동일 원칙).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-31
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    default = "1" if dialect == "sqlite" else "TRUE"
    column_type = "INTEGER" if dialect == "sqlite" else "BOOLEAN"
    op.execute(f"ALTER TABLE app_user ADD COLUMN is_active {column_type} NOT NULL DEFAULT {default}")
    op.execute(f"UPDATE app_user SET is_active = {default}")


def downgrade() -> None:
    op.execute("ALTER TABLE app_user DROP COLUMN is_active")
