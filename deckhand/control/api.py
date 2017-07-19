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
from deckhand.control import base as api_base
from deckhand.control import documents
from deckhand.control import secrets
from deckhand.db.sqlalchemy import api as db_api

CONF = cfg.CONF


def __setup_logging():
    LOGGER_NAME = CONF.logging.global_logger_name
    LOG = logging.getLogger(__name__, LOGGER_NAME)

    logging.register_options(CONF)

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

    logging.setup(CONF, LOGGER_NAME)
    LOG.debug('Initiated Deckhand logging.')


def start_api(state_manager=None):
    """Main entry point for initializing the Deckhand API service.

    Create routes for the v1.0 API and sets up logging.
    """
    config.register_opts(CONF)
    __setup_logging()
    engine = db_api.get_engine()
    assert engine.engine.name == 'postgres'

    control_api = falcon.API(request_type=api_base.DeckhandRequest)

    v1_0_routes = [
        ('documents', documents.DocumentsResource()),
        ('secrets', secrets.SecretsResource())
    ]

    for path, res in v1_0_routes:
        control_api.add_route(os.path.join('/api/v1.0', path), res)

    return control_api
