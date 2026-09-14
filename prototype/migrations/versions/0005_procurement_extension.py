"""03. Procurement Management 확장 (v11) — 공급업체평가/구매계약/외주구매구분/통관관리

1.0_AX_ERP_Menu_Structure.md의 "03. Procurement Management" 중 그동안 구현하지 않았던 항목을
추가한다(task-plan-v9-full-menu-rollout.md §3 v11 참고). 전부 신규 additive 테이블/컬럼이라
기존 데이터에는 영향이 없다.

- vendor_evaluation: 공급업체 평가(납기/품질/가격 점수, 100점 만점). 등록만(승인 불필요, 조회용 마스터).
- purchase_contract: 공급업체별 구매계약(기간/조건) 마스터 — sales_contract(v9)와 동일 패턴.
- import_customs_record: PO 단위 통관/수입 진행상황(간이 — 정식 관세사 연동 없음).
- purchase_order.po_type: STANDARD(일반)/OUTSOURCING(외주)/CONSIGNMENT(위탁) 구분 컬럼.
  원재료/부자재/설비/금형 구매는 신규 테이블 없이 기존 material.material_type 필터 뷰로 대체
  (task-plan §3 v11 명시 — 현재 시드 데이터의 material_type은 RM/FG만 존재).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_NEW_TABLES_REVERSE_ORDER = ["import_customs_record", "purchase_contract", "vendor_evaluation"]


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        num = "REAL"
        now_date = "TEXT NOT NULL DEFAULT (date('now'))"
    else:
        pk = "SERIAL PRIMARY KEY"
        num = "NUMERIC"
        now_date = "TEXT NOT NULL DEFAULT CURRENT_DATE"

    op.execute(f"""
        CREATE TABLE vendor_evaluation (
          eval_id {pk},
          vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
          eval_date {now_date},
          delivery_score {num} NOT NULL,
          quality_score {num} NOT NULL,
          price_score {num} NOT NULL,
          notes TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE purchase_contract (
          contract_id {pk},
          external_no TEXT UNIQUE,
          vendor_id INTEGER NOT NULL REFERENCES vendor(vendor_id),
          start_date TEXT NOT NULL,
          end_date TEXT,
          terms TEXT,
          status TEXT NOT NULL DEFAULT 'ACTIVE'
        )
    """)

    op.execute(f"""
        CREATE TABLE import_customs_record (
          customs_id {pk},
          po_id INTEGER NOT NULL REFERENCES purchase_order(po_id),
          declaration_no TEXT,
          customs_status TEXT NOT NULL DEFAULT 'PENDING',
          customs_date {now_date},
          notes TEXT
        )
    """)

    op.execute("ALTER TABLE purchase_order ADD COLUMN po_type TEXT NOT NULL DEFAULT 'STANDARD'")


def downgrade() -> None:
    op.execute("ALTER TABLE purchase_order DROP COLUMN po_type")
    for table in _NEW_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
