"""session 테이블에 디바이스 정보 컬럼 추가 (v8)

task-plan(2순위/3순위 — 세션 관리 UI) 참고.
- user_agent: 로그인/토큰 발급 시점의 User-Agent 헤더. 세션 목록 UI에서 "어떤 기기/브라우저"인지
  사람이 알아볼 수 있게 보여주기 위한 용도(정밀한 기기 판별이 목적이 아니라 사용자 스스로 낯선
  세션을 알아채도록 돕는 최소 정보).
- last_seen_at: 이 refresh token으로 마지막으로 재발급(rotate)되거나 발급된 시각. 세션 목록을
  "최근 활동순"으로 정렬하고, 오래 방치된 세션을 사용자가 구분할 수 있게 한다.

주의: schema_sqlite.sql/schema_postgres.sql은 수정하지 않는다 — 0001이 이 파일들을 실행 시점에
동적으로 읽으므로, 여기서 스키마 파일을 고치면 신규 설치 시 중복 컬럼 오류가 난다. v4 이후 스키마
변경은 전부 번호 붙은 마이그레이션 파일에만 남긴다(0002_session_rotation.py와 동일 원칙).

기존(0003 적용 이전) 세션 행은 last_seen_at을 created_at으로 백필한다 — NULL로 두면 세션 목록
정렬/표시가 부자연스러워진다.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE session ADD COLUMN user_agent TEXT")
    op.execute("ALTER TABLE session ADD COLUMN last_seen_at TEXT")
    op.execute("UPDATE session SET last_seen_at = created_at WHERE last_seen_at IS NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE session DROP COLUMN user_agent")
    op.execute("ALTER TABLE session DROP COLUMN last_seen_at")
