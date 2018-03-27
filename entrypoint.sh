#!/bin/bash
#
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

set -ex

# Define port
PORT=${PORT:-9000}
# How long uWSGI should wait for each deckhand response
DECKHAND_API_TIMEOUT=${DECKHAND_API_TIMEOUT:-"600"}

# NOTE(fmontei): Deckhand's database is not configured to work with
# multiprocessing. Currently there is a data race on acquiring shared
# SQLAlchemy engine pooled connection strings when workers > 1. As a
# workaround, we use multiple threads but only 1 worker. For more
# information, see: https://github.com/att-comdev/deckhand/issues/20

# Number of uWSGI workers to handle API requests
DECKHAND_API_WORKERS=${DECKHAND_API_WORKERS:-"1"}
# Threads per worker
DECKHAND_API_THREADS=${DECKHAND_API_THREADS:-"4"}
# The Deckhand configuration directory containing deckhand.conf
DECKHAND_CONFIG_DIR=${DECKHAND_CONFIG_DIR:-"/etc/deckhand/deckhand.conf"}

# Start deckhand application
exec uwsgi \
    -b 32768 \
    --callable deckhand_callable \
    --die-on-term \
    --enable-threads \
    --http :${PORT} \
    --http-timeout $DECKHAND_API_TIMEOUT \
    -L \
    --lazy-apps \
    --master \
    --pyargv "--config-file ${DECKHAND_CONFIG_DIR}/deckhand.conf" \
    --threads $DECKHAND_API_THREADS \
    --workers $DECKHAND_API_WORKERS \
    -w deckhand.cmd
