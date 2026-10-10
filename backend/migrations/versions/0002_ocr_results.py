"""OCR01: immutable file versions and cached derived page text."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_ocr_results"
down_revision = "0001_identity_blobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assets_file_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("original_blob_id", sa.Uuid(), sa.ForeignKey("assets_blobs.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_file_versions_file_id", "assets_file_versions", ["file_id"])
    op.create_table(
        "assets_ocr_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "file_version_id", sa.Uuid(), sa.ForeignKey("assets_file_versions.id"), nullable=False
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("preparation_profile", sa.String(200), nullable=False),
        sa.Column("prepared_sha256", sa.String(64), nullable=False),
        sa.Column("prepared_blob_id", sa.Uuid(), sa.ForeignKey("assets_blobs.id"), nullable=False),
        sa.Column("ocr_profile", JSONB, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("invocation", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page >= 1", name=op.f("ck_assets_ocr_results_positive_page")),
        sa.CheckConstraint(
            "length(btrim(text)) > 0", name=op.f("ck_assets_ocr_results_nonempty_text")
        ),
    )
    op.create_index(
        "ix_assets_ocr_results_file_version_id", "assets_ocr_results", ["file_version_id"]
    )


def downgrade():
    op.drop_table("assets_ocr_results")
    op.drop_table("assets_file_versions")
