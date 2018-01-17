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
# Number of uWSGI workers to handle API requests
DECKHAND_API_WORKERS=${DECKHAND_API_WORKERS:-"4"}
# Threads per worker
DECKHAND_API_THREADS=${DECKHAND_API_THREADS:-"1"}

# Start deckhand application
exec uwsgi \
    --http :${PORT} \
    -w deckhand.cmd \
    --callable deckhand_callable \
    --http-timeout $DECKHAND_API_TIMEOUT \
    --enable-threads \
    -L \
    --pyargv "--config-file /etc/deckhand/deckhand.conf" \
    --threads $DECKHAND_API_THREADS \
    --workers $DECKHAND_API_WORKERS
