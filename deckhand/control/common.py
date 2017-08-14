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

import functools


class ViewBuilder(object):
    """Model API responses as dictionaries."""

    _collection_name = None

    def _gen_url(self, revision):
        # TODO(fmontei): Use a config-based url for the base url below.
        base_url = 'https://deckhand/api/v1.0/%s/%s'
        return base_url % (self._collection_name, revision.get('id'))


def sanitize_params(allowed_params):
    """Sanitize query string parameters passed to an HTTP request.

    Overrides the ``params`` attribute in the ``req`` object with the sanitized
    params. Invalid parameters are ignored.

    :param allowed_params: The request's query string parameters.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, req, *func_args, **func_kwargs):
            req_params = req.params or {}
            sanitized_params = {}

            for key in req_params.keys():
                if key in allowed_params:
                    sanitized_params[key] = req_params[key]

            func_args = func_args + (sanitized_params,)
            return func(self, req, *func_args, **func_kwargs)

        return wrapper

    return decorator
