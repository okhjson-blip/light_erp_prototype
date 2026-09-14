"""01. Sales Management 확장 (v9) — 가격정책/견적/판매계약/반품/서비스오더 + 원가 컬럼

1.0_AX_ERP_Menu_Structure.md의 "01. Sales Management" 중 그동안 구현하지 않았던 항목을
추가한다(task-plan-v9-full-menu-rollout.md §3 v9 참고). 전부 신규 additive 테이블/컬럼이라
기존 데이터에는 영향이 없다.

- price_policy: 품목(+선택적 고객)별 기준단가. 견적/수주 단가 자동제안에 사용.
- quotation/quotation_line: 견적 → (승인 후) 수주 전환.
- sales_contract: 고객별 판매계약(기간/조건) 마스터, 등록/조회만(수주와 강한 연동은 비범위).
- sales_return/sales_return_line: 출하 완료된 수주에 대한 반품 접수 → 승인 시 재고 복원.
- service_order: AS/서비스 접수(11.Service Management와 테이블 공유 예정, v9에서는 접수/상태변경만).
- material.std_cost: 손익분석(고객별/제품별)에 쓸 표준원가 근사치. 없으면 0으로 간주(손익=매출 전체).

quotation/sales_return은 기존 approval_workflow(PR/PO와 동일한 범용 승인 테이블)에 등록해
승인함(GET /api/approvals, POST /api/approvals/{id}/decision)을 그대로 재사용한다 — 신규 승인
UI가 필요 없다.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_NEW_TABLES_REVERSE_ORDER = [
    "service_order", "sales_return_line", "sales_return",
    "sales_contract", "quotation_line", "quotation", "price_policy",
]


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
        CREATE TABLE price_policy (
          price_policy_id {pk},
          material_id INTEGER NOT NULL REFERENCES material(material_id),
          customer_id INTEGER REFERENCES customer(customer_id),
          unit_price {num} NOT NULL,
          valid_from {now_date},
          valid_to TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE quotation (
          quotation_id {pk},
          external_no TEXT UNIQUE,
          customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
          status TEXT NOT NULL DEFAULT 'DRAFT',
          quotation_date {now_date},
          converted_so_id INTEGER REFERENCES sales_order(so_id)
        )
    """)
    op.execute(f"""
        CREATE TABLE quotation_line (
          quotation_line_id {pk},
          quotation_id INTEGER NOT NULL REFERENCES quotation(quotation_id),
          material_id INTEGER NOT NULL REFERENCES material(material_id),
          qty {num} NOT NULL,
          unit_price {num} NOT NULL DEFAULT 0
        )
    """)

    op.execute(f"""
        CREATE TABLE sales_contract (
          contract_id {pk},
          external_no TEXT UNIQUE,
          customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
          start_date TEXT NOT NULL,
          end_date TEXT,
          terms TEXT,
          status TEXT NOT NULL DEFAULT 'ACTIVE'
        )
    """)

    op.execute(f"""
        CREATE TABLE sales_return (
          return_id {pk},
          external_no TEXT UNIQUE,
          so_id INTEGER NOT NULL REFERENCES sales_order(so_id),
          customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
          reason TEXT,
          status TEXT NOT NULL DEFAULT 'REQUESTED',
          created_date {now_date}
        )
    """)
    op.execute(f"""
        CREATE TABLE sales_return_line (
          return_line_id {pk},
          return_id INTEGER NOT NULL REFERENCES sales_return(return_id),
          material_id INTEGER NOT NULL REFERENCES material(material_id),
          qty {num} NOT NULL,
          warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id)
        )
    """)

    op.execute(f"""
        CREATE TABLE service_order (
          service_order_id {pk},
          external_no TEXT UNIQUE,
          customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
          material_id INTEGER REFERENCES material(material_id),
          symptom TEXT,
          status TEXT NOT NULL DEFAULT 'RECEIVED',
          created_date {now_date}
        )
    """)

    op.execute("ALTER TABLE material ADD COLUMN std_cost NUMERIC DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE material DROP COLUMN std_cost")
    for table in _NEW_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
