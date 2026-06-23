"""Merge heads

Revision ID: 511b73d5b1d3
Revises: 4c5d2f4d3b1e, cb886b73cc3c
Create Date: 2026-01-22 00:53:23.594565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '511b73d5b1d3'
down_revision = ('4c5d2f4d3b1e', 'cb886b73cc3c')
branch_labels = None
depends_on = None


def upgrade():
    # Merge migration: unifies two divergent migration heads.
    # It introduces no schema changes of its own, so the body is intentionally empty.
    pass


def downgrade():
    # No-op: a merge revision carries no schema changes, so there is nothing to reverse.
    pass
