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


def to_camel_case(s):
    """Convert string to camel case."""
    return (s[0].lower() + string.capwords(s, sep='_')
            .replace('_', '')[1:] if s else s)


def to_snake_case(name):
    """Convert string to snake case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def jsonpath_parse(document, jsonpath):
    """Parse value given JSON path in the document.

    Retrieve the value corresponding to document[jsonpath] where ``jsonpath``
    is a multi-part key. A multi-key is a series of keys and nested keys
    concatenated together with ".". For exampple, ``jsonpath`` of
    ".foo.bar.baz" should mean that ``document`` has the format:

    .. code-block:: yaml

       ---
       foo:
           bar:
               baz: <data_to_be_extracted_here>

    :param document: Dictionary used for extracting nested entry.
    :param jsonpath: A multi-part key that references nested data in a
        dictionary.
    :returns: Nested entry in ``document`` if present, else None.
    """
    if jsonpath.startswith('.'):
        jsonpath = '$' + jsonpath

    p = jsonpath_ng.parse(jsonpath)
    matches = p.find(document)
    if matches:
        return matches[0].value
