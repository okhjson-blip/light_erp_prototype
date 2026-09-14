"""session 테이블에 refresh token 회전(rotation) + 재사용 탐지용 컬럼 추가 (v6)

task-plan-refresh-rotation.md 참고.
- family_id: 로그인 1회당 발급되는 refresh token 계열(family) 식별자. 회전으로 새로 발급되는
  토큰도 같은 family_id를 유지한다.
- rotated_at: 이 토큰이 회전으로 폐기(교체)된 시각(NULL이면 아직 유효한 최신 토큰). 이미 폐기된
  토큰이 다시 제시되면 탈취로 간주해 family_id가 같은 모든 행을 즉시 삭제한다(app/auth.py 참고).

주의: schema_sqlite.sql/schema_postgres.sql은 수정하지 않는다 — 0001 마이그레이션이 이 파일들을
실행 시점에 동적으로 읽으므로, 여기서 스키마 파일을 고치면 신규 설치 시 0001이 이미 이 컬럼들을
만들어버려 아래 ADD COLUMN이 중복 오류를 낸다. v4 이후 스키마 변경은 전부 번호 붙은 마이그레이션
파일에만 남긴다.

기존(0002 적용 이전) 세션 행은 family_id를 자기 token 값으로 백필해 서로 다른 family로 분리한다 —
전부 빈 문자열로 두면 모든 레거시 세션이 하나의 family로 묶여, 한 세션의 재사용 탐지가 무관한 다른
사용자 세션까지 전부 무효화하는 사고가 날 수 있다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE session ADD COLUMN family_id TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE session ADD COLUMN rotated_at TEXT")
    op.execute("UPDATE session SET family_id = token WHERE family_id = ''")


def downgrade() -> None:
    op.execute("ALTER TABLE session DROP COLUMN family_id")
    op.execute("ALTER TABLE session DROP COLUMN rotated_at")
