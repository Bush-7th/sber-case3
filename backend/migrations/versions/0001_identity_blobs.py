"""INF01: server identities, hashed sessions and immutable bytea blobs."""

import sqlalchemy as sa
from alembic import op

revision = "0001_identity_blobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("identity_roles", sa.Column("name", sa.String(32), primary_key=True))
    op.bulk_insert(
        sa.table("identity_roles", sa.column("name", sa.String(32))),
        [{"name": "specialist"}, {"name": "administrator"}],
    )
    op.create_table(
        "identity_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(32), sa.ForeignKey("identity_roles.name"), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "identity_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("identity_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_identity_sessions_user_id", "identity_sessions", ["user_id"])
    op.create_index("ix_identity_sessions_expires_at", "identity_sessions", ["expires_at"])
    op.create_table(
        "assets_blobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_assets_blobs_nonnegative_size")),
        sa.CheckConstraint(
            "octet_length(data) = size_bytes", name=op.f("ck_assets_blobs_actual_size")
        ),
    )
    op.create_table(
        "assets_blob_references",
        sa.Column("blob_id", sa.Uuid(), sa.ForeignKey("assets_blobs.id"), primary_key=True),
        sa.Column("resource_id", sa.Uuid(), primary_key=True),
    )


def downgrade():
    op.drop_table("assets_blob_references")
    op.drop_table("assets_blobs")
    op.drop_table("identity_sessions")
    op.drop_table("identity_users")
    op.drop_table("identity_roles")
