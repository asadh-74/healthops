"""Add v2 platform tables; preserve legacy vaccine_stock and appointments."""

from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "001_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError("Forward-only migration: restore a verified backup to roll back.")
