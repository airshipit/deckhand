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

import re

import falcon


class ContextMiddleware(object):

    def __init__(self, routing_map):
        self.routing_map = routing_map

    def process_request(self, req, resp):
        # Determine whether the method is allowed.
        req_method = req.method
        req_uri = req.uri
        found = False

        for route_pattern, allowed_methods in self.routing_map.items():
            if re.match(route_pattern, req_uri):
                if req_method not in allowed_methods:
                    raise falcon.HTTPMethodNotAllowed(allowed_methods)
                else:
                    found = True
                    break

        if not found:
            raise falcon.HTTPMethodNotAllowed([])
