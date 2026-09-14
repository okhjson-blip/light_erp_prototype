"""initial schema (v1~v4 프로토타입 baseline)

프로토타입 v1~v4 동안 쌓인 전체 스키마를 그대로 재현하는 기준 마이그레이션이다. 이 시점부터
스키마 변경은 새 마이그레이션 파일(alembic revision)로 관리하고, app/schema_sqlite.sql /
schema_postgres.sql은 "이 마이그레이션이 만드는 결과물"의 참고 문서로만 남긴다.

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""
from pathlib import Path

from alembic import op

from app.database import _split_statements

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# DROP 순서(FK 역순) — downgrade에서 재사용
_TABLES_REVERSE_ORDER = [
    "ai_recommendation_log", "kpi_monthly", "finance_summary_monthly", "shipment",
    "quality_inspection", "demand_forecast",
    "integration_api_key", "serial_number", "lot_consumption", "lot",
    "integration_event_log", "audit_log", "approval_workflow",
    "accounting_line", "accounting_document",
    "inventory_transaction", "inventory",
    "production_result", "work_order", "production_order",
    "ap_invoice", "goods_receipt", "po_line", "purchase_order", "pr_line", "purchase_requisition",
    "sales_invoice", "delivery", "sales_order_line", "sales_order",
    "session", "user_role", "role", "app_user", "gl_account", "vendor", "customer",
    "bom", "material", "warehouse", "plant", "company",
]


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    fname = "schema_sqlite.sql" if dialect == "sqlite" else "schema_postgres.sql"
    script = (APP_DIR / fname).read_text(encoding="utf-8")
    for stmt in _split_statements(script):
        op.execute(stmt)


def downgrade() -> None:
    for table in _TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
