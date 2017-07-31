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


def multi_getattr(multi_key, dict_data):
    """Iteratively check for nested attributes in the YAML data.

    Check for nested attributes included in "dest" attributes in the data
    section of the YAML file. For example, a "dest" attribute of
    ".foo.bar.baz" should mean that the YAML data adheres to:

    .. code-block:: yaml

       ---
       foo:
           bar:
               baz: <data_to_be_substituted_here>

    :param multi_key: A multi-part key that references nested data in the
        substitutable part of the YAML data, e.g. ".foo.bar.baz".
    :param substitutable_data: The section of data in the YAML data that
        is intended to be substituted with secrets.
    :returns: nested entry in ``dict_data`` if present; else None.
    """
    attrs = multi_key.split('.')
    # Ignore the first attribute if it is "." as that is a self-reference.
    if attrs[0] == '':
        attrs = attrs[1:]

    data = dict_data
    for attr in attrs:
        if attr not in data:
            return None
        data = data.get(attr)

    return data
