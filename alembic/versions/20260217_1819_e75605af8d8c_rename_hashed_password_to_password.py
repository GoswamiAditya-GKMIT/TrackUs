"""rename_hashed_password_to_password

Revision ID: e75605af8d8c
Revises: f9a6aa7dc68d
Create Date: 2026-02-17 18:19:16.364126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e75605af8d8c'
down_revision: Union[str, None] = 'f9a6aa7dc68d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'hashed_password', new_column_name='password')


def downgrade() -> None:
    op.alter_column('users', 'password', new_column_name='hashed_password')
