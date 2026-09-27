"""Add revocable sessions and hashed rotating refresh credentials.

Old tblRefreshToken rows are retained but are no longer accepted by authentication.
All clients must log in again after deploying this migration and the new code.
"""
from alembic import op
import sqlalchemy as sa

revision = "a8c193d5e270"
down_revision = "c74e08a73fca"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tblAuthSessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id_fk", sa.Integer(), sa.ForeignKey("tblUsers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_tblAuthSessions_user_id_fk", "tblAuthSessions", ["user_id_fk"])
    op.create_index("uq_auth_session_active_user", "tblAuthSessions", ["user_id_fk"],
                    unique=True, postgresql_where=sa.text("revoked_at IS NULL"),
                    sqlite_where=sa.text("revoked_at IS NULL"))
    op.create_table("tblRefreshCredentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("tblAuthSessions.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_tblRefreshCredentials_session_id", "tblRefreshCredentials", ["session_id"])


def downgrade():
    op.drop_table("tblRefreshCredentials")
    op.drop_table("tblAuthSessions")
