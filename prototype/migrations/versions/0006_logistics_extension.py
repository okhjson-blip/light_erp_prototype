"""04. Logistics Management 확장 (v12) — 창고Location/컨테이너/운송/물류비/보험/클레임

1.0_AX_ERP_Menu_Structure.md의 "04. Logistics Management" 중 미구현 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v12 참고). 전부 신규 additive 테이블 + GL 계정 1행이라
기존 데이터에는 영향이 없다.

- warehouse_location: 창고 내 Location(Zone/Rack/Bin) 마스터 — WMS Location 개념 보강.
  재고 트랜잭션(inventory/lot)과의 연결은 비범위(Enterprise 단계) — 마스터 관리만.
- container: 컨테이너 관리(출하 연결은 선택 FK).
- shipment_transport: 운송관리(TMS 간이 — 배차 기록 수준, task-plan 명시).
- logistics_cost: 물류비(운송/보험/통관/하역) 입력 → 정산 시 회계 전표 연동.
- insurance_policy / logistics_claim: 보험·클레임 간이 마스터+등록.
- gl_account에 "5100 물류비"(EXP) 1행 추가 — 물류비 정산 전표의 차변 계정.
  (수출관리/수입관리 화면은 기존 shipment/import_customs_record 조회 재사용 — 신규 테이블 없음)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-11
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_NEW_TABLES_REVERSE_ORDER = [
    "logistics_claim", "insurance_policy", "logistics_cost",
    "shipment_transport", "container", "warehouse_location",
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
        CREATE TABLE warehouse_location (
          location_id {pk},
          warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
          code TEXT NOT NULL,
          name TEXT,
          location_type TEXT NOT NULL DEFAULT 'BIN',
          UNIQUE (warehouse_id, code)
        )
    """)

    op.execute(f"""
        CREATE TABLE container (
          container_id {pk},
          container_no TEXT NOT NULL,
          container_type TEXT NOT NULL DEFAULT '40FT',
          shipment_id INTEGER REFERENCES shipment(shipment_id),
          status TEXT NOT NULL DEFAULT 'EMPTY',
          notes TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE shipment_transport (
          transport_id {pk},
          shipment_id INTEGER NOT NULL REFERENCES shipment(shipment_id),
          carrier TEXT,
          vehicle_no TEXT,
          driver TEXT,
          transport_date {now_date},
          status TEXT NOT NULL DEFAULT 'PLANNED',
          freight_cost {num}
        )
    """)

    op.execute(f"""
        CREATE TABLE logistics_cost (
          cost_id {pk},
          shipment_id INTEGER REFERENCES shipment(shipment_id),
          cost_type TEXT NOT NULL,
          amount {num} NOT NULL,
          cost_date {now_date},
          settled INTEGER NOT NULL DEFAULT 0,
          acct_doc_id INTEGER REFERENCES accounting_document(doc_id),
          notes TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE insurance_policy (
          policy_id {pk},
          policy_no TEXT NOT NULL,
          insurer TEXT NOT NULL,
          coverage TEXT,
          valid_from TEXT,
          valid_to TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE logistics_claim (
          claim_id {pk},
          shipment_id INTEGER REFERENCES shipment(shipment_id),
          claim_type TEXT NOT NULL,
          amount {num},
          status TEXT NOT NULL DEFAULT 'OPEN',
          claim_date {now_date},
          notes TEXT
        )
    """)

    # 물류비 정산 전표의 차변 계정(비용). 코드 체계는 seed의 4자리 규칙을 따른다.
    op.execute("INSERT INTO gl_account (code, name, account_type) VALUES ('5100', '물류비', 'EXP')")


def downgrade() -> None:
    op.execute("DELETE FROM gl_account WHERE code='5100'")
    for t in _NEW_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {t}")
