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

CONFIG_FILES = {
    'conf': 'deckhand.conf',
    'paste': 'deckhand-paste.ini'
}
_NO_AUTH_CONFIG = 'noauth-paste.ini'


def _get_config_files(env=None):
    if env is None:
        env = os.environ

    config_files = CONFIG_FILES.copy()
    dirname = env.get('DECKHAND_CONFIG_DIR', '/etc/deckhand').strip()

    # Workaround the fact that this reads from a config file to determine which
    # paste.ini file to use for server instantiation. This chicken and egg
    # problem is solved by using ConfigParser below.
    conf_path = os.path.join(dirname, config_files['conf'])
    temp_conf = {}
    config_parser = cfg.ConfigParser(conf_path, temp_conf)
    config_parser.parse()
    use_development_mode = (
        temp_conf['DEFAULT'].get('development_mode') == ['true']
    )

    if use_development_mode:
        config_files['paste'] = _NO_AUTH_CONFIG
        LOG.warning('Development mode enabled - Keystone authentication '
                    'disabled.')

    return {
        key: os.path.join(dirname, file) for key, file in config_files.items()
    }


def setup_logging(conf):
    logging.set_defaults(default_log_levels=logging.get_default_log_levels())
    logging.setup(conf, 'deckhand')
    py_logging.captureWarnings(True)


def init_application():
    """Main entry point for initializing the Deckhand API service.

    Create routes for the v1.0 API and sets up logging.
    """
    config_files = _get_config_files()
    paste_file = config_files['paste']

    CONF([],
         project='deckhand',
         default_config_files=list(config_files.values()))

    setup_logging(CONF)

    policy.Enforcer(CONF)

    LOG.debug('Starting WSGI application using %s configuration file.',
              paste_file)

    db_api.setup_db(CONF.database.connection)

    app = deploy.loadapp('config:%s' % paste_file, name='deckhand_api')
    return app


if __name__ == '__main__':
    init_application()
