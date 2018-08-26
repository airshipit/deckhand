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

import concurrent.futures
import functools

import falcon
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import six

from deckhand.barbican import cache as barbican_cache
from deckhand.common import document as document_wrapper
from deckhand.db.sqlalchemy import api as db_api
from deckhand import engine
from deckhand.engine import cache as engine_cache
from deckhand.engine import secrets_manager
from deckhand import errors
from deckhand import types

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


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


def get_rendered_docs(revision_id, **filters):
    data = _retrieve_documents_for_rendering(revision_id, **filters)
    documents = document_wrapper.DocumentDict.from_list(data)
    encryption_sources = _resolve_encrypted_data(documents)
    try:
        return engine.render(
            revision_id,
            documents,
            encryption_sources=encryption_sources)
    except (errors.BarbicanClientException,
            errors.BarbicanServerException,
            errors.InvalidDocumentLayer,
            errors.InvalidDocumentParent,
            errors.InvalidDocumentReplacement,
            errors.IndeterminateDocumentParent,
            errors.LayeringPolicyNotFound,
            errors.MissingDocumentKey,
            errors.SubstitutionSourceDataNotFound,
            errors.SubstitutionSourceNotFound,
            errors.UnknownSubstitutionError,
            errors.UnsupportedActionMethod) as e:
        with excutils.save_and_reraise_exception():
            LOG.exception(e.format_message())
    except errors.EncryptionSourceNotFound as e:
        # This branch should be unreachable, but if an encryption source
        # wasn't found, then this indicates the controller fed bad data
        # to the engine, in which case this is a 500.
        e.code = 500
        raise e


def _retrieve_documents_for_rendering(revision_id, **filters):
    """Retrieve all necessary documents needed for rendering. If a layering
    policy isn't found in the current revision, retrieve it in a subsequent
    call and add it to the list of documents.
    """
    try:
        documents = db_api.revision_documents_get(revision_id, **filters)
    except errors.RevisionNotFound as e:
        LOG.exception(six.text_type(e))
        raise falcon.HTTPNotFound(description=e.format_message())

    if not any([d['schema'].startswith(types.LAYERING_POLICY_SCHEMA)
                for d in documents]):
        try:
            layering_policy_filters = {
                'deleted': False,
                'schema': types.LAYERING_POLICY_SCHEMA
            }
            layering_policy = db_api.document_get(
                **layering_policy_filters)
        except errors.DocumentNotFound as e:
            LOG.exception(e.format_message())
        else:
            documents.append(layering_policy)

    return documents


def _resolve_encrypted_data(documents):
    """Resolve unencrypted data from the secret storage backend.

    Submits concurrent requests to the secret storage backend for all
    secret references for which unecrypted data is required for future
    substitutions during the rendering process.

    :param documents: List of all documents for the current revision.
    :type documents: List[dict]
    :returns: Dictionary keyed with secret references, whose values are
        the corresponding unencrypted data.
    :rtype: dict

    """
    encryption_sources = {}
    secret_ref = lambda x: x.data
    is_encrypted = lambda x: x.is_encrypted and x.has_barbican_ref
    encrypted_documents = (d for d in documents if is_encrypted(d))

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=CONF.barbican.max_workers) as executor:
        future_to_document = {
            executor.submit(secrets_manager.SecretsManager.get,
                            secret_ref=secret_ref(d),
                            src_doc=d): d for d in encrypted_documents
        }
        for future in concurrent.futures.as_completed(future_to_document):
            document = future_to_document[future]
            try:
                unecrypted_data = future.result()
            except Exception as exc:
                msg = ('Failed to retrieve a required secret from the '
                       'configured secret storage service. Document: [%s,'
                       ' %s] %s. Secret ref: %s' % (
                           document.schema,
                           document.layer,
                           document.name,
                           secret_ref(document)))
                LOG.error(msg + '. Details: %s', exc)
                raise falcon.HTTPInternalServerError(description=msg)
            else:
                encryption_sources.setdefault(secret_ref(document),
                                              unecrypted_data)

    return encryption_sources
