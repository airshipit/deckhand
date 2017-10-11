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

import logging as py_logging
import os

from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import policy
from paste import deploy

from deckhand.db.sqlalchemy import api as db_api

CONF = cfg.CONF

logging.register_options(CONF)
LOG = logging.getLogger(__name__)

CONFIG_FILES = ['deckhand.conf', 'deckhand-paste.ini']


def _get_config_files(env=None):
    if env is None:
        env = os.environ
    dirname = env.get('OS_DECKHAND_CONFIG_DIR', '/etc/deckhand').strip()
    return [os.path.join(dirname, config_file) for config_file in CONFIG_FILES]


def setup_logging(conf):
    # Add additional dependent libraries that have unhelp bug levels
    extra_log_level_defaults = []

    logging.set_defaults(default_log_levels=logging.get_default_log_levels() +
                         extra_log_level_defaults)
    logging.setup(conf, 'deckhand')
    py_logging.captureWarnings(True)


def init_application():
    """Main entry point for initializing the Deckhand API service.

    Create routes for the v1.0 API and sets up logging.
    """
    config_files = _get_config_files()
    paste_file = config_files[-1]

    CONF([], project='deckhand', default_config_files=config_files)
    setup_logging(CONF)

    policy.Enforcer(CONF)

    LOG.debug('Starting WSGI application using %s configuration file.',
              paste_file)

    db_api.drop_db()
    db_api.setup_db()

    app = deploy.loadapp('config:%s' % paste_file, name='deckhand_api')
    return app


if __name__ == '__main__':
    init_application()
