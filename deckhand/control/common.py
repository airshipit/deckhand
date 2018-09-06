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

import falcon

from deckhand.barbican import cache as barbican_cache
from deckhand.engine import cache as engine_cache


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
        'tag': 'tags.[*].tag',
        # Mappings for sorting.
        'createdAt': 'created_at'
    }

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, req, *func_args, **func_kwargs):
            req_params = req.params or {}
            sanitized_params = {}
            # This maps which type should be enforced per query parameter.
            # Everything not included in type dict below is assumed to be a
            # string or a list of strings.
            type_dict = {
                'limit': {
                    'func': lambda x: abs(int(x)),
                    'type': int
                }
            }

            def _enforce_query_filter_type(key, val):
                cast_func = type_dict.get(key)
                if cast_func:
                    try:
                        cast_val = cast_func['func'](val)
                    except Exception:
                        raise falcon.HTTPInvalidParam(
                            'Query parameter %s must be of type %s.' % (
                                key, cast_func['type']),
                            key)
                else:
                    cast_val = val
                return cast_val

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
                param_val = _enforce_query_filter_type(key, val)

                if not isinstance(val, list):
                    val = [val]

                is_key_val_pair = isinstance(val, list) and '=' in val[0]

                if key in allowed_params:
                    if key in _mapping:
                        if is_key_val_pair:
                            _convert_to_dict(
                                sanitized_params, _mapping[key], val)
                        else:
                            sanitized_params[_mapping[key]] = param_val
                    else:
                        if is_key_val_pair:
                            _convert_to_dict(sanitized_params, key, val)
                        else:
                            sanitized_params[key] = param_val

            func_args = func_args + (sanitized_params,)
            return func(self, req, *func_args, **func_kwargs)

        return wrapper

    return decorator


def invalidate_cache_data():
    """Invalidate all data associated with document rendering."""
    barbican_cache.invalidate()
    engine_cache.invalidate()
