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

import json
import uuid

import falcon
from falcon import request
import six

from deckhand import errors


class BaseResource(object):
    """Base resource class for implementing API resources."""

    def __init__(self):
        self.authorized_roles = []

    def on_options(self, req, resp):
        self_attrs = dir(self)
        methods = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH']
        allowed_methods = []

        for m in methods:
            if 'on_' + m.lower() in self_attrs:
                allowed_methods.append(m)

        resp.headers['Allow'] = ','.join(allowed_methods)
        resp.status = falcon.HTTP_200

    # For authorizing access at the Resource level. A Resource requiring
    # finer-grained authorization at the method or instance level must
    # implement that in the request handlers
    def authorize_roles(self, role_list):
        authorized = set(self.authorized_roles)
        applied = set(role_list)

        if authorized.isdisjoint(applied):
            return False
        else:
            return True

    def req_json(self, req):
        if req.content_length is None or req.content_length == 0:
            return None

        if req.content_type is not None and req.content_type.lower() \
            == 'application/json':
            raw_body = req.stream.read(req.content_length or 0)

            if raw_body is None:
                return None

            try:
                return json.loads(raw_body.decode('utf-8'))
            except json.JSONDecodeError as jex:
                raise errors.InvalidFormat("%s: Invalid JSON in body: %s" % (
                    req.path, jex))
        else:
            raise errors.InvalidFormat("Requires application/json payload.")

    def return_error(self, resp, status_code, message="", retry=False):
        resp.body = json.dumps(
            {'type': 'error', 'message': six.text_type(message),
             'retry': retry})
        resp.status = status_code


class DeckhandRequestContext(object):

    def __init__(self):
        self.user = None
        self.roles = ['*']
        self.request_id = str(uuid.uuid4())

    def set_user(self, user):
        self.user = user

    def add_role(self, role):
        self.roles.append(role)

    def add_roles(self, roles):
        self.roles.extend(roles)

    def remove_role(self, role):
        if role in self.roles:
            self.roles.remove(role)


class DeckhandRequest(request.Request):
    context_type = DeckhandRequestContext
