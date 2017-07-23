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

    filters = models.Document.UNIQUE_CONSTRAINTS
    existing_document = document_get(**{c: values[c] for c in filters})

    created_document = {}

    def _document_changed():
        # The document has changed if at least one value in ``values`` differs.
        for key, val in values.items():
            if val != existing_document[key]:
                return True
        return False

    def _document_create():
        document = models.Document()
        with session.begin():
            document.update(values)
            document.save(session=session)
        return document.to_dict()

    if existing_document:
        # Only generate a new revision and entirely new document if anything
        # was changed.
        if _document_changed():
            created_document = _document_create()
            revision_update(created_document['id'], existing_document['id'])
    else:
        created_document = _document_create()
        revision_create(created_document['id'])

    return created_document


def document_get(session=None, **filters):
    session = session or get_session()
    document = session.query(models.Document).filter_by(**filters).first()
    return document.to_dict() if document else {}


####################


def revision_create(document_id, session=None):
    session = session or get_session()
    revision = models.Revision()
    with session.begin():
        revision.update({'document_id': document_id})
        revision.save(session=session)

    return revision.to_dict()


def revision_get(document_id, session=None):
    session = session or get_session()
    revision = session.query(models.Revision)\
        .filter_by(document_id=document_id).first()
    return revision.to_dict()


def revision_update(document_id, child_document_id, session=None):
    """Create a parent revision and update the child revision.

    The ``document_id`` references the newly created document that is a more
    up-to-date revision. Create a new (parent) revision that references
    ``document_id`` and whose ``child_id`` is ``child_document_id``.

    Set the ``parent_id`` for ``child_revision`` to ``document_id``.

    After this function has executed, the following relationship is true:

        parent_document <-- parent_revision
                  ^         /          
                   \     (has child)
                    \     /
                     \   /
                      \ /
                      / \
                     /   \
                    /     \
                   /     (has parent)
                  v         \
        child_document <-- child_revision

    :param document_id: The ID corresponding to the up-to-date document.
    :param child_document_id: The ID corresponding tothe out-of-date document.
    :param session: The database session.
    :returns: The dictionary representation of the newly created revision.
    """
    session = session or get_session()
    parent_revision = models.Revision()
    with session.begin():
        parent_revision.update({'document_id': document_id,
                                'child_id': child_document_id})   
        parent_revision.save(session=session)

    child_revision = session.query(models.Revision)\
        .filter_by(document_id=child_document_id).first()
    with session.begin():
        child_revision.update({'parent_id': document_id})
        child_revision.save(session=session)

    return parent_revision.to_dict()
