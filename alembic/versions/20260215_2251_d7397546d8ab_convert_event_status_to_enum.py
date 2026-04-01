"""convert_event_status_to_enum

Revision ID: d7397546d8ab
Revises: 58cba7904409
Create Date: 2026-02-15 22:51:45.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd7397546d8ab'
down_revision = '58cba7904409'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create event_status enum type
    event_status_enum = postgresql.ENUM(
        'PLANNED', 'ONGOING', 'COMPLETED', 'CANCELLED',
        name='event_status',
        create_type=True
    )
    event_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create participant_status enum type
    participant_status_enum = postgresql.ENUM(
        'INVITED', 'ACCEPTED', 'REJECTED', 'LEFT', 'REMOVED',
        name='participant_status',
        create_type=True
    )
    participant_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Convert travel_events.status column to use enum
    # First drop the default, then convert type, then re-add default
    op.alter_column('travel_events', 'status', server_default=None)
    op.execute("""
        ALTER TABLE travel_events 
        ALTER COLUMN status TYPE event_status 
        USING status::event_status
    """)
    op.alter_column('travel_events', 'status', server_default='PLANNED')
    
    # Convert event_participants.status column to use enum
    # First drop the default, then convert type, then re-add default
    op.alter_column('event_participants', 'status', server_default=None)
    op.execute("""
        ALTER TABLE event_participants 
        ALTER COLUMN status TYPE participant_status 
        USING status::participant_status
    """)
    op.alter_column('event_participants', 'status', server_default='INVITED')



def downgrade() -> None:
    # Convert back to VARCHAR
    op.execute("""
        ALTER TABLE travel_events 
        ALTER COLUMN status TYPE VARCHAR(20) 
        USING status::text
    """)
    
    op.execute("""
        ALTER TABLE event_participants 
        ALTER COLUMN status TYPE VARCHAR(20) 
        USING status::text
    """)
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS event_status")
    op.execute("DROP TYPE IF EXISTS participant_status")
