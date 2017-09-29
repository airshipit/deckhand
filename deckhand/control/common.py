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
    # A mapping between the filter keys users provide and the actual DB
    # representation of the filter.
    _mapping = {
        # Mappings for revision documents.
        'status.bucket': 'bucket_name',
        'metadata.label': 'metadata.labels',
        # Mappings for revisions.
        'tag': 'tags.[*].tag'
    }

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, req, *func_args, **func_kwargs):
            req_params = req.params or {}
            sanitized_params = {}

            def _convert_to_dict(sanitized_params, filter_key, filter_val):
                # Key-value pairs like metadata.label=foo=bar need to be
                # converted to {'metadata.label': {'foo': 'bar'}} because
                # 'metadata.labels' in a document is a dictionary. Later,
                # we can check whether the filter dict is a subset of the
                # actual dict for metadata labels.
                for val in list(filter_val):
                    if '=' in val:
                        sanitized_params.setdefault(filter_key, {})
                        pair = val.split('=')
                        try:
                            sanitized_params[filter_key][pair[0]] = pair[1]
                        except IndexError:
                            pass

            for key, val in req_params.items():
                if not isinstance(val, list):
                    val = [val]
                is_key_val_pair = '=' in val[0]
                if key in allowed_params:
                    if key in _mapping:
                        if is_key_val_pair:
                            _convert_to_dict(
                                sanitized_params, _mapping[key], val)
                        else:
                            sanitized_params[_mapping[key]] = req_params[key]
                    else:
                        if is_key_val_pair:
                            _convert_to_dict(sanitized_params, key, val)
                        else:
                            sanitized_params[key] = req_params[key]

            func_args = func_args + (sanitized_params,)
            return func(self, req, *func_args, **func_kwargs)

        return wrapper

    return decorator
