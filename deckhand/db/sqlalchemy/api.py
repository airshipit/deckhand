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


"""Defines interface for DB access."""

import copy
import datetime
import threading

from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db import options
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
from oslo_utils import excutils
import six
from six.moves import range
import sqlalchemy
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import desc
from sqlalchemy import MetaData, Table
import sqlalchemy.orm as sa_orm
from sqlalchemy import sql
import sqlalchemy.sql as sa_sql

from deckhand.db.sqlalchemy import models

sa_logger = None
LOG = logging.getLogger(__name__)

CONF = cfg.CONF

options.set_defaults(CONF)

_FACADE = None
_LOCK = threading.Lock()


def _retry_on_deadlock(exc):
    """Decorator to retry a DB API call if Deadlock was received."""

    if isinstance(exc, db_exception.DBDeadlock):
        LOG.warn("Deadlock detected. Retrying...")
        return True
    return False


def _create_facade_lazily():
    global _LOCK, _FACADE
    if _FACADE is None:
        with _LOCK:
            if _FACADE is None:
                _FACADE = session.EngineFacade.from_config(
                    CONF, sqlite_fk=True)
    return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()


def get_session(autocommit=True, expire_on_commit=False):
    facade = _create_facade_lazily()
    return facade.get_session(autocommit=autocommit,
                              expire_on_commit=expire_on_commit)


def _validate_db_int(**kwargs):
    """Make sure that all arguments are less than or equal to 2 ** 31 - 1.
    This limitation is introduced because databases stores INT in 4 bytes.
    If the validation fails for some argument, exception. Invalid is raised
    with appropriate information.
    """
    max_int = (2 ** 31) - 1

    for param_key, param_value in kwargs.items():
        if param_value and param_value > max_int:
            msg = _("'%(param)s' value out of range, "
                    "must not exceed %(max)d.") % {"param": param_key,
                                                   "max": max_int}
            raise exception.Invalid(msg)


def clear_db_env():
    """Unset global configuration variables for database."""
    global _FACADE
    _FACADE = None


def setup_db():
    models.register_models(get_engine())


def drop_db():
    models.unregister_models(get_engine())


def documents_create(documents, session=None):
    """Create a set of documents."""
    created_docs = [document_create(doc, session) for doc in documents]
    return created_docs


def document_create(values, session=None):
    """Create a document."""
    values = values.copy()
    values['doc_metadata'] = values.pop('metadata')
    values['schema_version'] = values.pop('schemaVersion')
    session = session or get_session()

    filters = copy.copy(models.Document.UNIQUE_CONSTRAINTS)
    filters = [f for f in filters if f != 'revision_index']
    existing_document = document_get(**{c: values[c] for c in filters})

    def _document_changed():
        other_document = copy.deepcopy(existing_document)
        other_document = other_document.to_dict()
        # The document has changed if at least one value in ``values`` differs.
        for key, val in values.items():
            if val != other_document[key]:
                return True
        return False

    def _document_create():
        document = models.Document()
        with session.begin():
            document.update(values)
            document.save(session=session)
        return document

    created_document = {}
    if existing_document:
        # Only generate a new revision and entirely new document if anything
        # was changed.
        if _document_changed():
            revision_index = revision_update(
                revision_index=existing_document['revision_index'])['id']
            values['revision_index'] = revision_index
            created_document = _document_create().to_dict()
        # TODO: indicate that now document was actually created.
    else:
        revision_index = revision_create()['id']
        values['revision_index'] = revision_index
        created_document = _document_create().to_dict()

    return created_document


def document_get(session=None, **filters):
    session = session or get_session()

    document = session.query(models.Document)\
        .filter_by(**filters)\
        .options(sa_orm.joinedload("revision_index"))\
        .order_by(desc(models.Revision.created_at))\
        .first()

    return document.to_dict() if document else {}


####################


def revision_create(session=None):
    session = session or get_session()
    revision = models.Revision()
    with session.begin():
        revision.save(session=session)

    return revision.to_dict()


def revision_update(session=None, revision_index=None):
    session = session or get_session()
    previous_revision = session.query(models.Revision).get(revision_index)

    new_revision = models.Revision()
    with session.begin():
        # Create the new revision with a reference to the previous revision.
        new_revision.update({'previous': revision_index})
        new_revision.save(session=session)

        # Update the previous revision with a reference to the new revision.
        previous_revision.update({'next': new_revision.id})
        previous_revision.save(session=session)

    return new_revision.to_dict()
