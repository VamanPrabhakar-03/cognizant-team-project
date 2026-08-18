"""Add ML priority inference fields to suspects."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_ml_priority_inference"
down_revision: Union[str, None] = "003_align_suspect_engine_output"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        sa.Column("ml_priority", sa.String(length=20), nullable=True),
        sa.Column("ml_priority_score", sa.Float(), nullable=True),
        sa.Column("ml_low_probability", sa.Float(), nullable=True),
        sa.Column("ml_medium_probability", sa.Float(), nullable=True),
        sa.Column("ml_high_probability", sa.Float(), nullable=True),
        sa.Column("ml_model_version", sa.String(length=50), nullable=True),
        sa.Column("ml_review_rank", sa.Integer(), nullable=True),
        sa.Column("ml_top_100", sa.Boolean(), nullable=True),
    ]
    with op.batch_alter_table("suspects") as batch_op:
        for column in columns:
            batch_op.add_column(column)
        batch_op.create_index("ix_suspects_ml_priority_score", ["ml_priority_score"])
        batch_op.create_index("ix_suspects_ml_review_rank", ["ml_review_rank"])
        batch_op.create_index("ix_suspects_ml_top_100", ["ml_top_100"])


def downgrade() -> None:
    with op.batch_alter_table("suspects") as batch_op:
        batch_op.drop_index("ix_suspects_ml_top_100")
        batch_op.drop_index("ix_suspects_ml_review_rank")
        batch_op.drop_index("ix_suspects_ml_priority_score")
        for name in [
            "ml_top_100", "ml_review_rank", "ml_model_version", "ml_high_probability",
            "ml_medium_probability", "ml_low_probability", "ml_priority_score", "ml_priority",
        ]:
            batch_op.drop_column(name)
