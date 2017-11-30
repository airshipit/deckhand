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
import string

import jsonpath_ng

from deckhand import errors


def to_camel_case(s):
    """Convert string to camel case."""
    return (s[0].lower() + string.capwords(s, sep='_')
            .replace('_', '')[1:] if s else s)


def to_snake_case(name):
    """Convert string to snake case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


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
    :returns: Entry that corresponds to ``data[jsonpath]`` if present,
        else None.

    Example::

        src_name = sub['src']['name']
        src_path = sub['src']['path']
        src_doc = db_api.document_get(schema=src_schema, name=src_name)
        src_secret = utils.jsonpath_parse(src_doc['data'], src_path)
        # Do something with the extracted secret from the source document.
    """
    if jsonpath.startswith('.'):
        jsonpath = '$' + jsonpath

    p = jsonpath_ng.parse(jsonpath)
    matches = p.find(data)
    if matches:
        result = [m.value for m in matches]
        return result if match_all else result[0]


def jsonpath_replace(data, value, jsonpath, pattern=None):
    """Update value in ``data`` at the path specified by ``jsonpath``.

    If the nested path corresponding to ``jsonpath`` isn't found in ``data``,
    the path is created as an empty ``{}`` for each sub-path along the
    ``jsonpath``.

    :param data: The `data` section of a document.
    :param value: The new value for ``data[jsonpath]``.
    :param jsonpath: A multi-part key that references a nested path in
        ``data``.
    :param pattern: A regular expression pattern.
    :returns: Updated value at ``data[jsonpath]``.
    :raises: MissingDocumentPattern if ``pattern`` is not None and
        ``data[jsonpath]`` doesn't exist.

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
    """
    data = data.copy()
    if jsonpath.startswith('.'):
        jsonpath = '$' + jsonpath

    def _do_replace():
        p = jsonpath_ng.parse(jsonpath)
        p_to_change = p.find(data)

        if p_to_change:
            _value = value
            if pattern:
                to_replace = p_to_change[0].value
                # `value` represents the value to inject into `to_replace` that
                # matches the `pattern`.
                try:
                    _value = re.sub(pattern, value, to_replace)
                except TypeError:
                    _value = None
            return p.update(data, _value)

    result = _do_replace()
    if result:
        return result

    # A pattern requires us to look up the data located at data[jsonpath]
    # and then figure out what re.match(data[jsonpath], pattern) is (in
    # pseudocode). But raise an exception in case the path isn't present in the
    # data and a pattern has been provided since it is impossible to do the
    # look up.
    if pattern:
        raise errors.MissingDocumentPattern(
            data=data, path=jsonpath, pattern=pattern)

    # However, Deckhand should be smart enough to create the nested keys in the
    # data if they don't exist and a pattern isn't required.
    d = data
    for path in jsonpath.split('.')[1:]:
        if path not in d:
            d.setdefault(path, {})
        d = d.get(path)

    return _do_replace()


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
