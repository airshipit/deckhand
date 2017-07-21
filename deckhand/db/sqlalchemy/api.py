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


def document_create(values, session=None):
    """Create a document."""
    values = values.copy()
    values['doc_metadata'] = values.pop('metadata')
    values['schema_version'] = values.pop('schemaVersion')

    session = session or get_session()
    document = models.Document()
    with session.begin():
        document.update(values)
        document.save(session=session)
    
    return document.to_dict()
