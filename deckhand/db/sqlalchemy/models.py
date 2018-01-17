# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_db.sqlalchemy import models
from oslo_db.sqlalchemy import types as oslo_types
from oslo_utils import timeutils
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext import declarative
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship
from sqlalchemy import String
from sqlalchemy import UniqueConstraint


# Declarative base class which maintains a catalog of classes and tables
# relative to that base.
BASE = declarative.declarative_base()


class DeckhandBase(models.ModelBase, models.TimestampMixin):
    """Base class for Deckhand Models."""

    __table_args__ = {'mysql_engine': 'Postgre', 'mysql_charset': 'utf8'}
    __table_initialized__ = False
    __protected_attributes__ = set([
        "created_at", "updated_at", "deleted_at", "deleted"])

    created_at = Column(DateTime, default=lambda: timeutils.utcnow(),
                        nullable=False)
    updated_at = Column(DateTime, default=lambda: timeutils.utcnow(),
                        nullable=True, onupdate=lambda: timeutils.utcnow())
    deleted_at = Column(DateTime, nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)

    def save(self, session=None):
        from deckhand.db.sqlalchemy import api as db_api
        super(DeckhandBase, self).save(session or db_api.get_session())

    def safe_delete(self, session=None):
        self.deleted = True
        self.deleted_at = timeutils.utcnow()
        super(DeckhandBase, self).save(session=session)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def to_dict(self):
        """Convert the object into dictionary format.
        """
        d = self.__dict__.copy()
        # Remove private state instance, as it is not serializable and causes
        # CircularReference.
        d.pop("_sa_instance_state")

        for k in ["created_at", "updated_at", "deleted_at"]:
            if k in d and d[k]:
                d[k] = d[k].isoformat()
            else:
                d.setdefault(k, None)

        return d


class Bucket(BASE, DeckhandBase):
    __tablename__ = 'buckets'

    id = Column(Integer, primary_key=True)
    name = Column(String(36), unique=True)
    documents = relationship("Document", backref="bucket")


class Revision(BASE, DeckhandBase):
    __tablename__ = 'revisions'

    id = Column(Integer, primary_key=True)
    # `primaryjoin` used below for sqlalchemy to distinguish between
    # `Document.revision_id` and `Document.orig_revision_id`.
    documents = relationship("Document",
                             primaryjoin="Revision.id==Document.revision_id")
    tags = relationship("RevisionTag")
    validations = relationship("Validation")

    def to_dict(self):
        d = super(Revision, self).to_dict()
        d['documents'] = [doc.to_dict() for doc in self.documents]
        d['tags'] = [tag.to_dict() for tag in self.tags]
        return d


class RevisionTag(BASE, DeckhandBase):
    __tablename__ = 'revision_tags'

    id = Column(Integer, primary_key=True)
    tag = Column(String(64), nullable=False)
    data = Column(oslo_types.JsonEncodedDict(), nullable=True, default={})
    revision_id = Column(
        Integer, ForeignKey('revisions.id', ondelete='CASCADE'),
        nullable=False)


class Document(BASE, DeckhandBase):
    UNIQUE_CONSTRAINTS = ('schema', 'name', 'revision_id')
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    schema = Column(String(64), nullable=False)
    # NOTE(fmontei): ``metadata`` is reserved by the DB, so ``_metadata``
    # must be used to store document metadata information in the DB.
    _metadata = Column(oslo_types.JsonEncodedDict(), nullable=False)
    data = Column(JSONB, nullable=True)
    data_hash = Column(String, nullable=False)
    metadata_hash = Column(String, nullable=False)
    bucket_id = Column(Integer, ForeignKey('buckets.id', ondelete='CASCADE'),
                       nullable=False)
    revision_id = Column(
        Integer, ForeignKey('revisions.id', ondelete='CASCADE'),
                            nullable=False)
    # Used for documents that haven't changed across revisions but still have
    # been carried over into newer revisions. This is necessary in order to
    # roll back to previous revisions or to generate a revision diff. Without
    # recording all the documents that were PUT in a revision, this is rather
    # difficult. By using `orig_revision_id` it is therefore possible to
    # maintain the correct revision history -- that is, remembering the exact
    # revision a document was created in -- while still being able to roll
    # back to all the documents that exist in a specific revision or generate
    # an accurate revision diff report.
    orig_revision_id = Column(
        Integer, ForeignKey('revisions.id', ondelete='CASCADE'),
                            nullable=True)

    UniqueConstraint(*UNIQUE_CONSTRAINTS)

    @hybrid_property
    def bucket_name(self):
        if hasattr(self, 'bucket') and self.bucket:
            return self.bucket.name
        return None

    def to_dict(self, raw_dict=False):
        """Convert the object into dictionary format.

        :param raw_dict: Renames the key "_metadata" to "metadata".
        """
        d = super(Document, self).to_dict()
        d['bucket_name'] = self.bucket_name

        if not raw_dict:
            d['metadata'] = d.pop('_metadata')

        if 'bucket' in d:
            d.pop('bucket')

        return d


class Validation(BASE, DeckhandBase):
    __tablename__ = 'validations'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    status = Column(String(8), nullable=False)
    validator = Column(oslo_types.JsonEncodedDict(), nullable=False)
    errors = Column(oslo_types.JsonEncodedList(), nullable=False, default=[])
    revision_id = Column(
        Integer, ForeignKey('revisions.id', ondelete='CASCADE'),
                            nullable=False)


def register_models(engine):
    """Create database tables for all models with the given engine."""
    models = [Bucket, Document, Revision, RevisionTag, Validation]
    for model in models:
        model.metadata.create_all(engine)


def unregister_models(engine):
    """Drop database tables for all models with the given engine."""
    models = [Bucket, Document, Revision, RevisionTag, Validation]
    for model in models:
        model.metadata.drop_all(engine)
