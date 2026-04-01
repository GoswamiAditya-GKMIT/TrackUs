"""add_unique_event_name_per_group

Revision ID: 0b6b9688c6d7
Revises: 1edd591d5850
Create Date: 2026-02-13 12:51:05.997005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b6b9688c6d7'
down_revision: Union[str, None] = '1edd591d5850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint on event name per group (excluding soft-deleted events)
    op.create_index(
        'idx_unique_event_name_per_group',
        'travel_events',
        ['group_id', 'name'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )


def downgrade() -> None:
    # Remove unique constraint
    op.drop_index('idx_unique_event_name_per_group', table_name='travel_events')
