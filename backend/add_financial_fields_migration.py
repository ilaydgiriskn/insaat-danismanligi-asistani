"""Add financial questions fields

Revision ID: add_financial_questions
Revises: 
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_financial_questions'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for financial questions
    op.add_column('user_profiles', sa.Column('savings_info', sa.String(length=500), nullable=True))
    op.add_column('user_profiles', sa.Column('credit_usage', sa.String(length=500), nullable=True))
    op.add_column('user_profiles', sa.Column('exchange_preference', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove columns if rolling back
    op.drop_column('user_profiles', 'exchange_preference')
    op.drop_column('user_profiles', 'credit_usage')
    op.drop_column('user_profiles', 'savings_info')
