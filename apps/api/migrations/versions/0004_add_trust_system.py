"""Add trust system: trust_level, trust_score, contact info, application details

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-17

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── opportunities ───────────────────────────────────────
    op.add_column("opportunities", sa.Column("trust_level", sa.String(30), nullable=False, server_default="UNVERIFIED"))
    op.add_column("opportunities", sa.Column("trust_score", sa.Float(), nullable=False, server_default="20.0"))
    op.add_column("opportunities", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("opportunities", sa.Column("application_url", sa.String(2000), nullable=True))
    op.add_column("opportunities", sa.Column("document_url", sa.String(2000), nullable=True))
    op.add_column("opportunities", sa.Column("application_type", sa.String(20), nullable=True))
    op.create_index("ix_opportunities_trust_level", "opportunities", ["trust_level"])

    # ─── scraping_sources ────────────────────────────────────
    op.add_column("scraping_sources", sa.Column("trust_level", sa.String(30), nullable=False, server_default="UNVERIFIED"))


def downgrade() -> None:
    op.drop_column("scraping_sources", "trust_level")
    op.drop_index("ix_opportunities_trust_level", table_name="opportunities")
    op.drop_column("opportunities", "application_type")
    op.drop_column("opportunities", "document_url")
    op.drop_column("opportunities", "application_url")
    op.drop_column("opportunities", "contact_email")
    op.drop_column("opportunities", "trust_score")
    op.drop_column("opportunities", "trust_level")
