"""INT01: durable application resources and leased verification jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_workflow"
down_revision = "0002_ocr_results"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_resources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("identity_users.id")),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("kind", "owner_id", "parent_id"):
        op.create_index("ix_workflow_resources_" + column, "workflow_resources", [column])
    op.create_table(
        "workflow_jobs",
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("workflow_resources.id"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("lease", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_jobs_status", "workflow_jobs", ["status"])


def downgrade():
    op.drop_table("workflow_jobs")
    op.drop_table("workflow_resources")
