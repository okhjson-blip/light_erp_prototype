"""07. Engineering(R&D) 신규 (v15) — ECO/도면/프로젝트/시제품/개발원가/표준부품

1.0_AX_ERP_Menu_Structure.md의 "07. Engineering (R&D)" 신규 구현
(task-plan-v9-full-menu-rollout.md §3 v15 참고). 전부 additive.

- eco_request: BOM 변경요청(ECO/ECR 통합 간이) — 기존 approval_workflow에 'ECO'로 등록해
  승인함 화면 재사용(v9 quotation/sales_return 패턴). 승인 시 bom 테이블에 자동 적용.
- drawing_doc: 도면 메타데이터+외부링크(파일 업로드는 비범위 — task-plan 명시).
- rnd_project / prototype_item / dev_cost: 프로젝트관리·시제품관리·개발원가관리(전부 간이).
- material.is_standard_part: 부품/설계 표준화 — 표준부품 지정 플래그(마스터 통합의 프로토타입 티어 해석).
  BOM 관리 UI는 기존 bom 테이블 조회(신규 테이블 없음 — 백엔드 트리 전개는 app/engineering.py).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-11
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_NEW_TABLES_REVERSE_ORDER = ["dev_cost", "prototype_item", "rnd_project", "drawing_doc", "eco_request"]


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        num = "REAL"
    else:
        pk = "SERIAL PRIMARY KEY"
        num = "NUMERIC"

    op.execute("ALTER TABLE material ADD COLUMN is_standard_part INTEGER NOT NULL DEFAULT 0")

    op.execute(f"""
        CREATE TABLE eco_request (
          eco_id {pk},
          title TEXT NOT NULL,
          parent_material_id INTEGER NOT NULL REFERENCES material(material_id),
          change_type TEXT NOT NULL,
          child_material_id INTEGER NOT NULL REFERENCES material(material_id),
          new_qty {num},
          reason TEXT,
          status TEXT NOT NULL DEFAULT 'PENDING',
          applied INTEGER NOT NULL DEFAULT 0,
          request_date TEXT NOT NULL,
          applied_date TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE drawing_doc (
          drawing_id {pk},
          material_id INTEGER NOT NULL REFERENCES material(material_id),
          doc_no TEXT NOT NULL,
          title TEXT,
          revision TEXT NOT NULL DEFAULT 'A',
          file_url TEXT,
          created_date TEXT NOT NULL
        )
    """)

    op.execute(f"""
        CREATE TABLE rnd_project (
          project_id {pk},
          name TEXT NOT NULL,
          owner TEXT,
          start_date TEXT,
          end_date TEXT,
          status TEXT NOT NULL DEFAULT 'PLANNED',
          budget {num},
          notes TEXT
        )
    """)

    op.execute(f"""
        CREATE TABLE prototype_item (
          proto_id {pk},
          project_id INTEGER NOT NULL REFERENCES rnd_project(project_id),
          material_id INTEGER REFERENCES material(material_id),
          name TEXT NOT NULL,
          stage TEXT NOT NULL DEFAULT 'DESIGN',
          test_result TEXT,
          created_date TEXT NOT NULL
        )
    """)

    op.execute(f"""
        CREATE TABLE dev_cost (
          cost_id {pk},
          project_id INTEGER NOT NULL REFERENCES rnd_project(project_id),
          cost_type TEXT NOT NULL,
          amount {num} NOT NULL,
          cost_date TEXT NOT NULL,
          notes TEXT
        )
    """)


def downgrade() -> None:
    for t in _NEW_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {t}")
    dialect = op.get_bind().dialect.name
    if dialect != "sqlite":
        op.execute("ALTER TABLE material DROP COLUMN is_standard_part")
