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
from oslo_serialization import jsonutils as json
from oslo_utils import timeutils
from sqlalchemy import Column
from sqlalchemy.ext import declarative
from sqlalchemy import Integer
from sqlalchemy import orm
from sqlalchemy import schema
from sqlalchemy import String
from sqlalchemy import types


class _DeckhandBase(models.ModelBase, models.TimestampMixin):
    pass


# Declarative base class which maintains a catalog of classes and tables
# relative to that base.
API_BASE = declarative.declarative_base(cls=_DeckhandBase)


class JSONEncodedDict(types.TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict(255)

    """

    impl = types.VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class Document(API_BASE):
    __tablename__ = 'document'
    __table_args__ = (schema.UniqueConstraint('schema_version', 'kind',
                      name='uniq_schema_version_kinds0schema_version0kind'),)

    id = Column(String(255), primary_key=True, autoincrement=True)
    revision_index = Column(Integer, nullable=False)
    schema_version = Column(String(64), nullable=False)
    kind = Column(String(64), nullable=False)
    # NOTE: Do not define a maximum length for these JSON data below. However,
    # this approach is not compatible with all database types.
    # "metadata" is reserved, so use "doc_metadata" instead.
    doc_metadata = Column(JSONEncodedDict(), nullable=False)
    data = Column(JSONEncodedDict(), nullable=False)
