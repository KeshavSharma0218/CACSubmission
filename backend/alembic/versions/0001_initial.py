"""Create the initial SafeWalk schema with PostGIS spatial indexes."""
from alembic import op
from app.database.database import Base
from app.database import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
