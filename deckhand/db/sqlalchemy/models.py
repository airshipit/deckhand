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

import uuid

from oslo_db.sqlalchemy import models
from oslo_serialization import jsonutils as json
from oslo_utils import timeutils
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.ext import declarative
from sqlalchemy import Integer
from sqlalchemy import orm
from sqlalchemy import schema
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


# Declarative base class which maintains a catalog of classes and tables
# relative to that base.
BASE = declarative.declarative_base()


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict(255)

    """

    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class DeckhandBase(models.ModelBase, models.TimestampMixin):
    """Base class for Deckhand Models."""

    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}
    __table_initialized__ = False
    __protected_attributes__ = set([
        "created_at", "updated_at", "deleted_at", "deleted"])

    def save(self, session=None):
        from deckhand.db.sqlalchemy import api as db_api
        super(DeckhandBase, self).save(session or db_api.get_session())

    created_at = Column(DateTime, default=lambda: timeutils.utcnow(),
                        nullable=False)
    updated_at = Column(DateTime, default=lambda: timeutils.utcnow(),
                        nullable=True, onupdate=lambda: timeutils.utcnow())
    deleted_at = Column(DateTime, nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)

    def delete(self, session=None):
        """Delete this object."""
        self.deleted = True
        self.deleted_at = timeutils.utcnow()
        self.save(session=session)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def to_dict(self):
        d = self.__dict__.copy()
        # Remove private state instance, as it is not serializable and causes
        # CircularReference.
        d.pop("_sa_instance_state")
        return d


class Document(BASE, DeckhandBase):
    __tablename__ = 'document'
    __table_args__ = (schema.UniqueConstraint('schema_version', 'kind',
                      name='ix_documents_schema_version_kind'),)

    id = Column(String(36), primary_key=True,
                default=lambda: str(uuid.uuid4()))
    revision_index = Column(String(36), nullable=False,
                            default=lambda: str(uuid.uuid4()))
    schema_version = Column(String(64), nullable=False)
    kind = Column(String(64), nullable=False)
    # NOTE: Do not define a maximum length for these JSON data below. However,
    # this approach is not compatible with all database types.
    # "metadata" is reserved, so use "doc_metadata" instead.
    doc_metadata = Column(JSONEncodedDict(), nullable=False)
    data = Column(JSONEncodedDict(), nullable=False)


def register_models(engine):
    """Create database tables for all models with the given engine."""
    models = [Document]
    for model in models:
        model.metadata.create_all(engine)


def unregister_models(engine):
    """Drop database tables for all models with the given engine."""
    models = [Document]
    for model in models:
        model.metadata.drop_all(engine)
