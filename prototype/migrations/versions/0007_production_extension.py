"""05. Production Management 확장 (v13) — 외주생산/재작업/생산마감

1.0_AX_ERP_Menu_Structure.md의 "05. Production Management" 중 미구현 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v13 참고). 전부 additive.

- production_order.is_outsourced / vendor_id: 외주생산 구분 + 외주처(v11 po_type과 동일 패턴 —
  승인 워크플로 불필요한 단순 분류 컬럼).
- rework_order: 불량 시리얼 재투입 플로우(OPEN → REWORKED(시리얼 IN_STOCK 복귀) / SCRAPPED).
- production_close: 월별 생산마감(마감 후 해당월 실적입력 잠금 + FI 전표 연동).
  MRP/OEE분석/생산Dashboard는 신규 테이블 없이 기존 bom/demand_forecast/inventory/po_line/
  production_result 집계 조회로 구현(app/production_ext.py).

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-11
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        num = "REAL"
    else:
        pk = "SERIAL PRIMARY KEY"
        num = "NUMERIC"

    op.execute("ALTER TABLE production_order ADD COLUMN is_outsourced INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE production_order ADD COLUMN vendor_id INTEGER REFERENCES vendor(vendor_id)")

    op.execute(f"""
        CREATE TABLE rework_order (
          rework_id {pk},
          serial_id INTEGER NOT NULL REFERENCES serial_number(serial_id),
          reason TEXT,
          status TEXT NOT NULL DEFAULT 'OPEN',
          created_date TEXT NOT NULL,
          completed_date TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE production_close (
          close_id {pk},
          period TEXT NOT NULL UNIQUE,
          total_good {num} NOT NULL DEFAULT 0,
          total_defect {num} NOT NULL DEFAULT 0,
          close_amount {num} NOT NULL DEFAULT 0,
          acct_doc_id INTEGER REFERENCES accounting_document(doc_id),
          closed_date TEXT NOT NULL,
          notes TEXT
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_close")
    op.execute("DROP TABLE IF EXISTS rework_order")
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        # SQLite ALTER TABLE DROP COLUMN은 3.35+에서만 — 프로토타입 downgrade는 컬럼 잔존 허용(0004/0005와 동일)
        pass
    else:
        op.execute("ALTER TABLE production_order DROP COLUMN vendor_id")
        op.execute("ALTER TABLE production_order DROP COLUMN is_outsourced")
