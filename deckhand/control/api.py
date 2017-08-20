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

import os

import falcon
from oslo_config import cfg
from oslo_log import log as logging

from deckhand.conf import config
from deckhand.control import base
from deckhand.control import buckets
from deckhand.control import middleware
from deckhand.control import revision_documents
from deckhand.control import revisions
from deckhand.control import secrets
from deckhand.db.sqlalchemy import api as db_api

CONF = cfg.CONF
LOG = None


def __setup_logging():
    global LOG

    logging.register_options(CONF)
    config.parse_args()

    current_path = os.path.dirname(os.path.realpath(__file__))
    root_path = os.path.abspath(os.path.join(current_path, os.pardir,
                                             os.pardir))
    logging_cfg_path = "%s/etc/deckhand/logging.conf" % root_path

    # If logging conf is in place we need to set log_config_append. Only do so
    # if the log path already exists.
    if ((not hasattr(CONF, 'log_config_append') or
        CONF.log_config_append is None) and
        os.path.isfile(logging_cfg_path)):
        CONF.log_config_append = logging_cfg_path

    logging.setup(CONF, 'deckhand')
    LOG = logging.getLogger(__name__, 'deckhand')
    LOG.debug('Initiated Deckhand logging.')


def __setup_db():
    db_api.drop_db()
    db_api.setup_db()


def _get_routing_map():
    ROUTING_MAP = {
        '/api/v1.0/bucket/.+/documents': ['PUT'],
        '/api/v1.0/revisions': ['GET', 'DELETE'],
        '/api/v1.0/revisions/.+': ['GET'],
        '/api/v1.0/revisions/documents': ['GET']
    }

    for route in ROUTING_MAP.keys():
        # Denote the start of the regex with "^".
        route_re = '^.*' + route
        # Debite the end of the regex with "$". Allow for an optional "/" at
        # the end of each request uri.
        route_re = route_re + '[/]{0,1}$'
        ROUTING_MAP[route_re] = ROUTING_MAP.pop(route)

    return ROUTING_MAP


def start_api(state_manager=None):
    """Main entry point for initializing the Deckhand API service.

    Create routes for the v1.0 API and sets up logging.
    """
    __setup_logging()
    __setup_db()

    control_api = falcon.API(
        request_type=base.DeckhandRequest,
        middleware=[middleware.ContextMiddleware(_get_routing_map())])

    v1_0_routes = [
        ('bucket/{bucket_name}/documents', buckets.BucketsResource()),
        ('revisions', revisions.RevisionsResource()),
        ('revisions/{revision_id}', revisions.RevisionsResource()),
        ('revisions/{revision_id}/documents',
         revision_documents.RevisionDocumentsResource()),
        # TODO(fmontei): remove in follow-up commit.
        ('secrets', secrets.SecretsResource())
    ]

    for path, res in v1_0_routes:
        control_api.add_route(os.path.join('/api/v1.0', path), res)

    return control_api
