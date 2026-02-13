"""add_travel_events_table

Revision ID: 1edd591d5850
Revises: 9f4a457fb75f
Create Date: 2026-02-12 23:51:45.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1edd591d5850'
down_revision: Union[str, None] = '9f4a457fb75f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create travel_events table
    op.create_table(
        'travel_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('destination', sa.String(length=100), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PLANNED'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.CheckConstraint('start_time < end_time', name='valid_time_range')
    )
    
    # Create indexes
    op.create_index('idx_events_group', 'travel_events', ['group_id'])
    op.create_index('idx_events_tenant', 'travel_events', ['tenant_id'])
    op.create_index('idx_events_deleted', 'travel_events', ['deleted_at'])
    op.create_index('idx_events_start_time', 'travel_events', ['start_time'])


def downgrade() -> None:
    op.drop_index('idx_events_start_time', table_name='travel_events')
    op.drop_index('idx_events_deleted', table_name='travel_events')
    op.drop_index('idx_events_tenant', table_name='travel_events')
    op.drop_index('idx_events_group', table_name='travel_events')
    op.drop_table('travel_events')
