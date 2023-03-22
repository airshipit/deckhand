"""initial deckhand base

Revision ID: 918bbfd28185
Revises:
Create Date: 2018-04-04 17:19:24.222703

"""
import logging
import six

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '918bbfd28185'
down_revision = None
branch_labels = None
depends_on = None

LOG = logging.getLogger('alembic.runtime.migration')

tables_select = text("""
select table_name from information_schema.tables where table_schema = 'public'
 and table_name in ('buckets', 'revisions','documents', 'revision_tags',
 'validations')
""")

check_documents_columns = text("""
select column_name from information_schema.columns
 where table_name = 'documents' and column_name in ('_metadata', 'layer')
""")

get_constraints = text("""
select conname from pg_constraint
""")

convert_layer = text("""
update documents d1 set layer = (
    select meta->'layeringDefinition'->>'layer' from documents d2
    where d2.id = d1.id)
""")


def upgrade():

    # Need to check if the tables exist first.
    # If they do, then we can't create them, and rather need to:
    #   check if documents has _metadata or meta column
    #       rename to meta if it does.
    #   check if documents.layer exists
    #       if not, add it and populate it from
    #       metadata.layeringDefinition.layer in the associated document
    # If the tables don't exist it is a new environment; create tables.
    #
    # Note that this is not fool-proof, if we have environments that are
    # not in a state accounted for in this migration, the migration will fail
    # This is easist and best if this first migration is starting from an
    # empty database.
    #
    # IMPORTANT Note:
    # It is irregular for migrations to conditionally apply changes.
    # Migraitons are generally straightforward application of changes -- e.g.
    # crate tables, drop columns, etc...
    # Do not model future migrations after this migration, which is specially
    # crafted to coerce non-Alembic manageed databases into an Alembic-managed
    # form.

    conn = op.get_bind()
    LOG.info("Finding tables with query: %s", tables_select)
    rs = conn.execute(tables_select)
    existing_tables = [row[0] for row in rs]
    LOG.info("Existing tables: %s", six.text_type(existing_tables))

    if 'buckets' not in existing_tables:
        LOG.info("'buckets' not present. Creating table")
        op.create_table('buckets',
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=36), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            mysql_charset='utf8',
            mysql_engine='Postgre'
        )

    if 'revisions' not in existing_tables:
        LOG.info("'revisions' not present. Creating table")
        op.create_table('revisions',
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            mysql_charset='utf8',
            mysql_engine='Postgre'
        )

    if 'documents' not in existing_tables:
        LOG.info("'documents' not present. Creating table")
        op.create_table('documents',
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('schema', sa.String(length=64), nullable=False),
            sa.Column('layer', sa.String(length=64), nullable=True),
            sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('data_hash', sa.String(), nullable=False),
            sa.Column('metadata_hash', sa.String(), nullable=False),
            sa.Column('bucket_id', sa.Integer(), nullable=False),
            sa.Column('revision_id', sa.Integer(), nullable=False),
            sa.Column('orig_revision_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['bucket_id'], ['buckets.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['orig_revision_id'], ['revisions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['revision_id'], ['revisions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('schema', 'layer', 'name', 'revision_id', name='duplicate_document_constraint')
        )
    else:
        # documents has undergone some changes that need to be accounted for
        # in this migration to ensure a common base.
        LOG.info("Finding columns in 'documents' table with query: %s",
                 check_documents_columns)
        rs = conn.execute(check_documents_columns)
        columns = [row[0] for row in rs]
        LOG.info("Columns are: %s", six.text_type(columns))

        if '_metadata' in columns:
            LOG.info("Found '_metadata' column; will rename to 'meta'")
            op.alter_column('documents', '_metadata', nullable=False,
                            new_column_name='meta')
            LOG.info("'_metadata' renamed to 'meta'")
        if 'layer' not in columns:
            LOG.info("'layer' column is not present. Adding column and"
                     " extracting data from meta column")

            # remove the constraint that is being modified
            rs = conn.execute(get_constraints)
            constraints = [row[0] for row in rs]

            if 'duplicate_document_constraint' in constraints:
                op.drop_constraint('duplicate_document_constraint',
                                   'documents')

            # add the layer column to documents
            op.add_column('documents',
                sa.Column('layer', sa.String(length=64), nullable=True)
            )

            # convert the data from meta to here.
            conn.execute(convert_layer)

            # add the constraint back in with the wole set of columns
            op.create_unique_constraint('duplicate_document_constraint',
                'documents', ['schema', 'layer', 'name', 'revision_id']
            )
            LOG.info("'layer' column added and initialized")

    if 'revision_tags' not in existing_tables:
        LOG.info("'revision_tags' not present. Creating table")
        op.create_table('revision_tags',
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tag', sa.String(length=64), nullable=False),
            sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('revision_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['revision_id'], ['revisions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            mysql_charset='utf8',
            mysql_engine='Postgre'
        )

    if 'validations' not in existing_tables:
        LOG.info("'validations' not present. Creating table")
        op.create_table('validations',
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=8), nullable=False),
            sa.Column('validator', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('revision_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['revision_id'], ['revisions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            mysql_charset='utf8',
            mysql_engine='Postgre'
        )

def downgrade():
    op.drop_table('validations')
    op.drop_table('revision_tags')
    op.drop_table('documents')
    op.drop_table('revisions')
    op.drop_table('buckets')
