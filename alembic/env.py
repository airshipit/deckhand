# Generated file from Alembic, modified portions copyright follows:
# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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
from __future__ import with_statement
import logging
from logging.config import fileConfig
import os

from alembic import context
from oslo_config import cfg
from sqlalchemy import engine_from_config, pool

from deckhand.db.sqlalchemy import api as db_api
from deckhand.db.sqlalchemy import models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)


# Portions modified for Deckhand Specifics:
# Set up and retrieve the config file for Deckhand. Sets up the oslo_config
logger = logging.getLogger('alembic.env')
CONF = cfg.CONF
dirname = os.environ.get('DECKHAND_CONFIG_DIR', '/etc/deckhand').strip()
config_files = [os.path.join(dirname, 'deckhand.conf')]
CONF([], project='deckhand', default_config_files=config_files)
logger.info("Database Connection: %s", CONF.database.connection)
config.set_main_option('sqlalchemy.url', CONF.database.connection)
models.register_models(db_api.get_engine(),
                       CONF.database.connection)
target_metadata = models.BASE.metadata
# End Deckhand Specifics


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
