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
from oslo_db.sqlalchemy import types as oslo_types
from oslo_utils import timeutils
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.ext import declarative
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship
from sqlalchemy import schema
from sqlalchemy import String


# Declarative base class which maintains a catalog of classes and tables
# relative to that base.
BASE = declarative.declarative_base()


class DeckhandBase(models.ModelBase, models.TimestampMixin):
    """Base class for Deckhand Models."""

    __table_args__ = {'mysql_engine': 'Postgre', 'mysql_charset': 'utf8'}
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

    def to_dict(self, raw_dict=False):
        """Conver the object into dictionary format.

        :param raw_dict: if True, returns unmodified data; else returns data
            expected by users.
        """
        d = self.__dict__.copy()
        # Remove private state instance, as it is not serializable and causes
        # CircularReference.
        d.pop("_sa_instance_state")

        if 'deleted_at' not in d:
            d.setdefault('deleted_at', None)

        for k in ["created_at", "updated_at", "deleted_at", "deleted"]:
            if k in d and d[k]:
                d[k] = d[k].isoformat()

        # NOTE(fmontei): ``metadata`` is reserved by the DB, so ``_metadata``
        # must be used to store document metadata information in the DB.
        if not raw_dict and '_metadata' in self.keys():
            d['metadata'] = d['_metadata']

        return d

    @staticmethod
    def gen_unqiue_contraint(*fields):
        constraint_name = 'ix_' + DeckhandBase.__name__.lower() + '_'
        for field in fields:
            constraint_name = constraint_name + '_%s' % field
        return schema.UniqueConstraint(*fields, name=constraint_name)


class Revision(BASE, DeckhandBase):
    __tablename__ = 'revisions'

    id = Column(String(36), primary_key=True,
                default=lambda: str(uuid.uuid4()))
    documents = relationship("Document")
    validation_policies = relationship("ValidationPolicy")

    def to_dict(self):
        d = super(Revision, self).to_dict()
        d['documents'] = [doc.to_dict() for doc in self.documents]
        d['validation_policies'] = [
            vp.to_dict() for vp in self.validation_policies]
        return d


class DocumentMixin(object):
    """Mixin class for sharing common columns across all document resources
    such as documents themselves, layering policies and validation policies.
    """

    name = Column(String(64), nullable=False)
    schema = Column(String(64), nullable=False)
    # NOTE: Do not define a maximum length for these JSON data below. However,
    # this approach is not compatible with all database types.
    # "metadata" is reserved, so use "_metadata" instead.
    _metadata = Column(oslo_types.JsonEncodedDict(), nullable=False)
    data = Column(oslo_types.JsonEncodedDict(), nullable=False)

    @declarative.declared_attr
    def revision_id(cls):
        return Column(Integer, ForeignKey('revisions.id'), nullable=False)


class Document(BASE, DeckhandBase, DocumentMixin):
    UNIQUE_CONSTRAINTS = ('schema', 'name', 'revision_id')
    __tablename__ = 'documents'
    __table_args__ = (DeckhandBase.gen_unqiue_contraint(*UNIQUE_CONSTRAINTS),)

    id = Column(String(36), primary_key=True,
                default=lambda: str(uuid.uuid4()))


class LayeringPolicy(BASE, DeckhandBase, DocumentMixin):

    # NOTE(fmontei): Only one layering policy can exist per revision, so
    # enforce this constraint at the DB level.
    UNIQUE_CONSTRAINTS = ('revision_id',)
    __tablename__ = 'layering_policies'
    __table_args__ = (DeckhandBase.gen_unqiue_contraint(*UNIQUE_CONSTRAINTS),)

    id = Column(String(36), primary_key=True,
                default=lambda: str(uuid.uuid4()))


class ValidationPolicy(BASE, DeckhandBase, DocumentMixin):

    UNIQUE_CONSTRAINTS = ('schema', 'name', 'revision_id')
    __tablename__ = 'validation_policies'
    __table_args__ = (DeckhandBase.gen_unqiue_contraint(*UNIQUE_CONSTRAINTS),)

    id = Column(String(36), primary_key=True,
                default=lambda: str(uuid.uuid4()))


def register_models(engine):
    """Create database tables for all models with the given engine."""
    models = [Document, Revision, LayeringPolicy, ValidationPolicy]
    for model in models:
        model.metadata.create_all(engine)


def unregister_models(engine):
    """Drop database tables for all models with the given engine."""
    models = [Document, Revision, LayeringPolicy, ValidationPolicy]
    for model in models:
        model.metadata.drop_all(engine)
