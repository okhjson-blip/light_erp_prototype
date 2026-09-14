"""06. Quality Management 확장 (v14) — 검사기준/8D/고객클레임/CAPA

1.0_AX_ERP_Menu_Structure.md의 "06. Quality Management" 중 미구현 항목을 추가한다
(task-plan-v9-full-menu-rollout.md §3 v14 참고). 전부 additive.

- inspection_standard: 품목×검사구분(INCOMING/IN_PROCESS/FINAL)별 검사항목 마스터(규격 LSL/USL 포함
  — SPC Cp/Cpk 계산의 기준값).
- eight_d_report: 8D Report 간이 폼(D2 문제/D4 근본원인/D5 시정조치만 — 전체 D1~D8 양식은 Enterprise 이연).
- customer_claim: 고객클레임 등록/처리.
- capa_action: CAPA 등록/처리 워크플로(기존 quality_inspection.capa_required='Y' 조회전용 → 실행 관리로 승격).
  검사구분(수입/공정/출하)은 기존 quality_inspection.inspection_type 컬럼을 그대로 사용(신규 컬럼 불필요
  — v1 스키마부터 존재), SPC/공정능력분석은 조회 API(app/quality_ext.py)로 구현.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-11
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_NEW_TABLES_REVERSE_ORDER = ["capa_action", "customer_claim", "eight_d_report", "inspection_standard"]


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        num = "REAL"
    else:
        pk = "SERIAL PRIMARY KEY"
        num = "NUMERIC"

    op.execute(f"""
        CREATE TABLE inspection_standard (
          standard_id {pk},
          material_id INTEGER NOT NULL REFERENCES material(material_id),
          inspection_type TEXT NOT NULL,
          item_name TEXT NOT NULL,
          method TEXT,
          spec_target {num},
          spec_lsl {num},
          spec_usl {num},
          unit TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE eight_d_report (
          report_id {pk},
          material_id INTEGER REFERENCES material(material_id),
          inspection_id INTEGER REFERENCES quality_inspection(inspection_id),
          title TEXT NOT NULL,
          problem TEXT,
          root_cause TEXT,
          corrective_action TEXT,
          status TEXT NOT NULL DEFAULT 'OPEN',
          report_date TEXT NOT NULL,
          closed_date TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE customer_claim (
          claim_id {pk},
          customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
          material_id INTEGER REFERENCES material(material_id),
          claim_type TEXT NOT NULL DEFAULT 'QUALITY',
          description TEXT,
          qty {num},
          status TEXT NOT NULL DEFAULT 'OPEN',
          claim_date TEXT NOT NULL,
          resolved_date TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE capa_action (
          capa_id {pk},
          source TEXT NOT NULL DEFAULT 'INSPECTION',
          inspection_id INTEGER REFERENCES quality_inspection(inspection_id),
          title TEXT NOT NULL,
          action_type TEXT NOT NULL DEFAULT 'CORRECTIVE',
          status TEXT NOT NULL DEFAULT 'OPEN',
          due_date TEXT,
          created_date TEXT NOT NULL,
          completed_date TEXT,
          notes TEXT
        )
    """)


def downgrade() -> None:
    for t in _NEW_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {t}")
