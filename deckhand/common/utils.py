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

import ast
import copy
import re
import six
import string

from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
import jsonpath_ng
from oslo_log import log as logging

from deckhand.common.document import DocumentDict as document_dict
from deckhand.conf import config
from deckhand import errors

CONF = config.CONF
LOG = logging.getLogger(__name__)

# Cache for JSON paths computed from path strings because jsonpath_ng
# is computationally expensive.
_CACHE_OPTS = {
    'cache.type': 'memory',
    'expire': CONF.jsonpath.cache_timeout,
}
_CACHE = CacheManager(**parse_cache_config_options(_CACHE_OPTS))

_ARRAY_RE = re.compile(r'.*\[\d+\].*')


def to_camel_case(s):
    """Convert string to camel case."""
    return (s[0].lower() + string.capwords(s, sep='_')
            .replace('_', '')[1:] if s else s)


def to_snake_case(name):
    """Convert string to snake case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', six.text_type(name))
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _normalize_jsonpath(jsonpath):
    """Changes jsonpath starting with a `.` character with a `$`"""
    if jsonpath == '.':
        jsonpath = '$'
    elif jsonpath.startswith('.'):
        jsonpath = '$' + jsonpath
    return jsonpath


@_CACHE.cache()
def _jsonpath_parse(jsonpath):
    """Retrieve the parsed jsonpath path

    Utilizes a cache of parsed values to eliminate re-parsing
    """
    return jsonpath_ng.parse(jsonpath)


def jsonpath_parse(data, jsonpath, match_all=False):
    """Parse value in the data for the given ``jsonpath``.

    Retrieve the nested entry corresponding to ``data[jsonpath]``. For
    example, a ``jsonpath`` of ".foo.bar.baz" means that the data section
    should conform to:

    .. code-block:: yaml

        ---
        foo:
            bar:
                baz: <data_to_be_extracted_here>

    :param data: The `data` section of a document.
    :param jsonpath: A multi-part key that references a nested path in
        ``data``.
    :param match_all: Whether to return all matches or just the first one.
    :returns: Entry that corresponds to ``data[jsonpath]`` if present,
        else None.

    Example::

        src_name = sub['src']['name']
        src_path = sub['src']['path']
        src_doc = db_api.document_get(schema=src_schema, name=src_name)
        src_secret = utils.jsonpath_parse(src_doc['data'], src_path)
        # Do something with the extracted secret from the source document.
    """
    jsonpath = _normalize_jsonpath(jsonpath)
    p = _jsonpath_parse(jsonpath)

    matches = p.find(data)
    if matches:
        result = [m.value for m in matches]
        return result if match_all else result[0]


def _execute_replace(data, value, jsonpath, pattern=None, recurse=None):
    # These are O(1) reference copies to avoid accidentally modifying source
    # data. We only want to update destination data.
    data_copy = copy.copy(data)
    value_copy = copy.copy(value)

    path = _jsonpath_parse(jsonpath)
    path_to_change = path.find(data_copy)
    recurse = recurse or {}

    def _try_replace_pattern(to_replace):
        try:
            # A pattern requires us to look up the data located at
            # to_replace[jsonpath] and then figure out what
            # re.match(to_replace[jsonpath], pattern) is (in pseudocode).
            # Raise an exception in case the path isn't present in the
            # to_replace and a pattern has been provided since it is
            # otherwise impossible to do the look-up.
            replacement = re.sub(pattern,
                                 six.text_type(value_copy),
                                 to_replace)
        except TypeError as e:
            LOG.error('Failed to substitute the value %s into %s '
                      'using pattern %s. Details: %s',
                      six.text_type(value_copy), to_replace, pattern,
                      six.text_type(e))
            raise errors.MissingDocumentPattern(jsonpath=jsonpath,
                                                pattern=pattern)
        return replacement

    def _replace_pattern_recursively(curr_data, depth, max_depth=-1):
        # If max_depth is -1 (meaning no depth), then recursion will be
        # performed over all of ``curr_data`` as depth starts out at 0.
        if depth == max_depth:
            return

        if isinstance(curr_data, dict):
            for k, v in curr_data.items():
                if isinstance(v, six.string_types) and pattern in v:
                    replacement = _try_replace_pattern(v)
                    curr_data[k] = replacement
                else:
                    _replace_pattern_recursively(v, depth + 1, max_depth)
        elif isinstance(curr_data, list):
            for idx, v in enumerate(curr_data):
                if isinstance(v, six.string_types) and pattern in v:
                    replacement = _try_replace_pattern(v)
                    curr_data[idx] = replacement
                else:
                    _replace_pattern_recursively(v, depth + 1, max_depth)

    to_replace = path_to_change[0].value
    if pattern:
        if recurse:
            max_depth = recurse.get('depth', -1)
            # Recursion is only possible for lists/dicts.
            if isinstance(to_replace, (dict, list)):
                _replace_pattern_recursively(to_replace, 0, max_depth)
                return data_copy
            else:
                # Edge case to handle a path that leads to a string value
                # (not a list or dict). Even though no recursion is
                # technically possible, gracefully handle this by
                # performing non-recursive pattern replacement on the str.
                return path.update(data_copy, _try_replace_pattern(to_replace))
        else:
            return path.update(data_copy, _try_replace_pattern(to_replace))
    else:
        return path.update(data_copy, value_copy)


def _execute_data_expansion(data, jsonpath):
    # Expand ``data`` with any path specified in ``jsonpath``. For example,
    # if jsonpath is ".foo[0].bar.baz" then for each subpath -- foo[0], bar,
    # and baz -- that key will be added to ``data`` if missing.
    d = data
    for path in jsonpath.split('.')[1:]:
        # Handle case where an array needs to be created.
        if _ARRAY_RE.match(path):
            try:
                path_pieces = path.split('[')
                path_piece = path_pieces[0]
                path_index = int(path_pieces[1][:-1])

                d.setdefault(path_piece, [])
                while len(d[path_piece]) < (path_index + 1):
                    d[path_piece].append({})

                d = d[path_piece][path_index]

                continue
            except (IndexError, ValueError):
                pass
        # Handle case where an object needs to be created.
        elif path not in d:
            if '\'' or '\"' in path:
                path = path.strip('\'').strip('\"')
            d.setdefault(path, {})
        d = d.get(path)


def jsonpath_replace(data, value, jsonpath, pattern=None, recurse=None,
                     src_pattern=None, src_match_group=0):
    """Update value in ``data`` at the path specified by ``jsonpath``.

    If the nested path corresponding to ``jsonpath`` isn't found in ``data``,
    the path is created as an empty ``{}`` for each sub-path along the
    ``jsonpath``.

    Example::

        doc = {
            'data': {
                'some_url': http://admin:INSERT_PASSWORD_HERE@svc-name:8080/v1
            }
        }
        secret = 'super-duper-secret'
        path = '$.some_url'
        pattern = 'INSERT_[A-Z]+_HERE'
        replaced_data = utils.jsonpath_replace(
            doc['data'], secret, path, pattern)
        # The returned URL will look like:
        # http://admin:super-duper-secret@svc-name:8080/v1
        doc['data'].update(replaced_data)

    :param data: The ``data`` section of a document.
    :param value: The new value for ``data[jsonpath]``.
    :param jsonpath: A multi-part key that references a nested path in
        ``data``. Must begin with "." or "$" (without quotes).
    :param pattern: A regular expression pattern.
    :param recurse: Dictionary containing a single key called "depth" which
        specifies the recursion depth. If provided, indicates that recursive
        pattern substitution should be performed, beginning at ``jsonpath``.
        Best practice is to limit the scope of the recursion as much as
        possible: e.g. avoid passing in "$" as the ``jsonpath``, but rather
        a JSON path that lives closer to the nested strings in question.
        Optimize performance by choosing an ideal ``depth`` value; -1 will
        cause recursion depth to be infinite.
    :param src_pattern: An optional regular expression pattern to apply to the
        source ``value``. The pattern is applied using re.search(), and may
        include parenthesized subgroups. Only the matched portion of ``value``
        is considered when substituting into the destination document.
    :param src_match_group: The numbered subgroup of the ``src_pattern`` match
        to use as the substitution source, where 0 (the default) represents the
        entire match, 1 is the first parenthesized subgroup, etc.
    :returns: Updated value at ``data[jsonpath]``.
    :raises: MissingDocumentPattern if ``pattern`` is not None and
        ``data[jsonpath]`` doesn't exist.
    :raises ValueError: If ``jsonpath`` doesn't begin with "."

    """

    # These are O(1) reference copies to avoid accidentally modifying source
    # data. We only want to update destination data.
    data_copy = copy.copy(data)
    value_copy = copy.copy(value)

    # If a src_pattern is specified, attempt a regex match.
    if src_pattern:
        if not isinstance(value_copy, six.string_types):
            err = 'not a string: {}' % value_copy
            LOG.error(err)
            raise ValueError(err)
        result = re.search(src_pattern, value_copy)
        if not result:
            LOG.warn("no match found, using entire value")
        else:
            value_copy = result.group(src_match_group)

    jsonpath = _normalize_jsonpath(jsonpath)
    recurse = recurse or {}

    if not jsonpath == '$' and not jsonpath.startswith('$.'):
        LOG.error('The provided jsonpath %s does not begin with "." or "$"',
                  jsonpath)
        # TODO(felipemonteiro): Use a custom internal exception for this.
        raise ValueError('The provided jsonpath %s does not begin with "." '
                         'or "$"' % jsonpath)

    # Deckhand should be smart enough to create the nested keys in the
    # data if they don't exist and a pattern isn't required.
    path = _jsonpath_parse(jsonpath)
    path_to_change = path.find(data_copy)
    if not path_to_change:
        _execute_data_expansion(data_copy, jsonpath)
    return _execute_replace(data_copy, value_copy, jsonpath, pattern=pattern,
                            recurse=recurse)


def multisort(data, sort_by=None, order_by=None):
    """Sort a dictionary by multiple keys.

    The order of the keys is important. The first key takes precedence over
    the second key, and so forth.

    :param data: Dictionary to be sorted.
    :param sort_by: list or string of keys to sort ``data`` by.
    :type sort_by: list or string
    :returns: Sorted dictionary by each key.
    """
    if sort_by is None:
        sort_by = 'created_at'
    if order_by not in ['asc', 'desc']:
        order_by = 'asc'
    if not isinstance(sort_by, list):
        sort_by = [sort_by]

    return sorted(data, key=lambda d: [
        jsonpath_parse(d, sort_key) for sort_key in sort_by],
        reverse=True if order_by == 'desc' else False)


def deepfilter(dct, **filters):
    """Match ``dct`` against all the filters in ``filters``.

    Check whether ``dct`` matches all the fitlers in ``filters``. The filters
    can reference nested attributes, attributes that are contained within
    other dictionaries within ``dct``.

    Useful for querying whether ``metadata.name`` or
    ``metadata.layeringDefinition.layerOrder`` match specific values.

    :param dct: The dictionary to check against all the ``filters``.
    :type dct: dict
    :param filters: Dictionary of key-value pairs used for filtering out
        unwanted results.
    :type filters: dict
    :returns: True if the dictionary satisfies all the filters, else False.
    """
    def _transform_filter_bool(filter_val):
        # Transform boolean values into string literals.
        if isinstance(filter_val, six.string_types):
            try:
                filter_val = ast.literal_eval(filter_val.title())
            except ValueError:
                # If not True/False, set to None to avoid matching
                # `actual_val` which is always boolean.
                filter_val = None
        return filter_val

    for filter_key, filter_val in filters.items():
        # If the filter is a list of possibilities, e.g. ['site', 'region']
        # for metadata.layeringDefinition.layer, check whether the actual
        # value is present.
        if isinstance(filter_val, (list, tuple)):
            actual_val = jsonpath_parse(dct, filter_key, match_all=True)
            if not actual_val:
                return False

            if isinstance(actual_val[0], bool):
                filter_val = [_transform_filter_bool(x) for x in filter_val]

            if not set(actual_val).intersection(set(filter_val)):
                return False
        else:
            actual_val = jsonpath_parse(dct, filter_key)

            # Else if both the filter value and the actual value in the doc
            # are dictionaries, check whether the filter dict is a subset
            # of the actual dict.
            if (isinstance(actual_val, dict) and
                    isinstance(filter_val, dict)):
                is_subset = set(
                    filter_val.items()).issubset(set(actual_val.items()))
                if not is_subset:
                    return False
            # Else both filters are string literals.
            else:
                # Filtering by schema must support namespace matching
                # (e.g. schema=promenade) such that all kind and schema
                # documents with promenade namespace are returned, or
                # (e.g. schema=promenade/Node) such that all version
                # schemas with namespace=schema and kind=Node are returned.
                if isinstance(actual_val, bool):
                    filter_val = _transform_filter_bool(filter_val)

                if filter_key in ['schema', 'metadata.schema']:
                    parts = actual_val.split('/')[:2]
                    if len(parts) == 2:
                        actual_namespace, actual_kind = parts
                    elif len(parts) == 1:
                        actual_namespace = parts[0]
                        actual_kind = ''
                    else:
                        actual_namespace = actual_kind = ''
                    actual_minus_version = actual_namespace + '/' + actual_kind

                    if not (filter_val == actual_val or
                            actual_minus_version == filter_val or
                            actual_namespace == filter_val):
                        return False
                else:
                    if actual_val != filter_val:
                        return False

    return True


def redact_document(document):
    """Redact ``data`` and ``substitutions`` sections for ``document``.

    :param dict document: Document whose data to redact.
    :returns: Document with redacted data.
    :rtype: dict
    """
    doc = _to_document(document)
    if doc.is_encrypted:
        doc.data = document_dict.redact(doc.data)
        for sub in doc.substitutions:
            sub['src']['path'] = document_dict.redact(sub['src']['path'])
            if isinstance(sub['dest'], list):
                for dest in sub['dest']:
                    dest['path'] = document_dict.redact(dest['path'])
            else:
                sub['dest']['path'] = document_dict.redact(sub['dest']['path'])
    return doc


def redact_documents(documents):
    """Redact sensitive data for each document in ``documents``.

    Sensitive data includes ``data``, ``substitutions[n].src.path``, and
    ``substitutions[n].dest.path`` fields.

    :param list[dict] documents: List of documents whose data to redact.
    :returns: Documents with redacted sensitive data.
    :rtype: list[dict]
    """
    return [redact_document(d) for d in documents]


def _to_document(document):
    clazz = document_dict
    if not isinstance(document, clazz):
        document = clazz(document)
    return document
