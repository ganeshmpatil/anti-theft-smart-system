"""Initial schema with provisioned flag

Revision ID: 001_initial
Revises:
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add provisioned column to devices table (for existing deployments)
    op.add_column("devices", sa.Column("provisioned", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("devices", "provisioned")
