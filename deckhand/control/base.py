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

import falcon
from oslo_log import log as logging
import yaml

from deckhand import context

LOG = logging.getLogger(__name__)


class BaseResource(object):
    """Base resource class for implementing API resources."""

    # Shadowing no_authentication_methods and supplying the HTTP method as a
    # value (e.g. 'GET') allows that method to run without authentication. By
    # default all require authentication.
    # Warning: This method of skipping authentication is applied to a HTTP
    # method, which ultimately maps to a resource's on_ methods.
    # If a method such as on_get were to service both a list and a single
    # response, both would share the skipped authentication.
    no_authentication_methods = []

    def on_options(self, req, resp):
        self_attrs = dir(self)

        methods = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH']
        allowed_methods = []

        for m in methods:
            if 'on_' + m.lower() in self_attrs:
                allowed_methods.append(m)

        resp.headers['Allow'] = ','.join(allowed_methods)
        resp.status = falcon.HTTP_200

    def from_yaml(self, req, expect_list=True, allow_empty=False):
        """Reads and converts YAML-formatted request body into a dict or list
        of dicts.

        :param req: Falcon Request object.
        :param expect_list: Whether to expect a list or an object.
        :param allow_empty: Whether the request body can be empty.
        :returns: List of dicts if ``expect_list`` is True or else a dict.
        """
        raw_data = req.stream.read(req.content_length or 0)

        if not allow_empty and not raw_data:
            error_msg = ("The request body must not be empty.")
            LOG.error(error_msg)
            raise falcon.HTTPBadRequest(description=error_msg)

        try:
            if expect_list:
                data = list(yaml.safe_load_all(raw_data))
            else:
                data = yaml.safe_load(raw_data)
        except yaml.YAMLError as e:
            error_msg = ("The request body must be properly formatted YAML. "
                         "Details: %s." % e)
            LOG.error(error_msg)
            raise falcon.HTTPBadRequest(description=error_msg)

        if expect_list:
            bad_entries = [str(i + 1) for i, x in enumerate(data)
                           if not x or not isinstance(x, dict)]
            if bad_entries:
                error_msg = (
                    "Expected a list of valid objects. Invalid entries "
                    "found at following indexes: %s." % ','.join(bad_entries))
                LOG.error(error_msg)
                raise falcon.HTTPBadRequest(description=error_msg)

        return data


class DeckhandRequest(falcon.Request):
    context_type = context.RequestContext

    @property
    def project_id(self):
        return self.context.tenant

    @property
    def user_id(self):
        return self.context.user

    @property
    def roles(self):
        return self.context.roles

    def __repr__(self):
        return '%s, context=%s' % (self.path, self.context)
