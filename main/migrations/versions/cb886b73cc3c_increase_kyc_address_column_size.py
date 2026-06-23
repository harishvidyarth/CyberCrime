"""increase_kyc_address_column_size

Revision ID: cb886b73cc3c
Revises: 639e2a9d0ff7
Create Date: 2025-12-12 20:57:34.995018

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb886b73cc3c'
down_revision = '639e2a9d0ff7'
branch_labels = None
depends_on = None


def upgrade():
    # Intentionally empty under Alembic: the kyc_address column size is enforced at
    # runtime by the app's ensure_columns() bootstrap (see ensure_transaction_columns
    # in app.py), so no DDL is applied here. This revision only advances history.
    pass


def downgrade():
    # No-op: the upgrade applies no DDL, so there is nothing to reverse.
    pass
