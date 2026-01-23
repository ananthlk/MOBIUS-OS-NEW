"""fix_proceed_indicator_constraint

Add 'red' to the allowed values for proceed_indicator check constraint.

Revision ID: b1c2d3e4f5g6
Revises: a9b8c7d6e5f4
Create Date: 2026-01-23 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old constraint and add new one with 'red' and 'purple' included
    op.drop_constraint('check_proceed_indicator', 'system_response', type_='check')
    op.create_check_constraint(
        'check_proceed_indicator',
        'system_response',
        "proceed_indicator IN ('grey', 'green', 'yellow', 'blue', 'red', 'purple')"
    )


def downgrade() -> None:
    # Restore old constraint (without 'red')
    op.drop_constraint('check_proceed_indicator', 'system_response', type_='check')
    op.create_check_constraint(
        'check_proceed_indicator',
        'system_response',
        "proceed_indicator IN ('grey', 'green', 'yellow', 'blue')"
    )
