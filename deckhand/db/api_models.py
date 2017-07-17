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

import json

from oslo_db.sqlalchemy import models
from oslo_utils import timeutils
import sqlalchemy as sa
from sqlalchemy.ext import declarative
from sqlalchemy import orm as sa_orm
from sqlalchemy import types as sa_types


class _DeckhandBase(models.ModelBase, models.TimestampMixin):
    pass


# Declarative base class which maintains a catalog of classes and tables
# relative to that base.
API_BASE = declarative.declarative_base(cls=_DeckhandBase)


class JSONEncodedDict(sa_types.TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict(255)

    """

    impl = sa_types.VARCHAR

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

    id = sa.Column(sa.String(255), primary_key=True, autoincrement=True)
    revision_index = sa.Column(sa.Integer, nullable=False)
    document_schema = sa.Column(sa.String(64), nullable=False)
    instance_key = sa.Column(sa.String(64), nullable=False, unique=True)
    document_metadata = sa.Column(JSONEncodedDict(), nullable=False)
    document_data = sa.Column(JSONEncodedDict(), nullable=False)
