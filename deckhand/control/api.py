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

from deckhand.control import base as api_base
from deckhand.control import secrets


def start_api(state_manager=None):
    """Start the Deckhand API service.

    Create routes for the v1.0 API.
    """
    control_api = falcon.API(request_type=api_base.DeckhandRequest)

    v1_0_routes = [
        ('/secrets', secrets.SecretsResource())
    ]

    for path, res in v1_0_routes:
        control_api.add_route(os.path.join('/api/v1.0', path), res)

    return control_api
