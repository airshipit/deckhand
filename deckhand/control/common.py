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

import string


def to_camel_case(s):
    return (s[0].lower() + string.capwords(s, sep='_').replace('_', '')[1:]
            if s else s)


class ViewBuilder(object):
    """Model API responses as dictionaries."""

    _collection_name = None

    def _gen_url(self, revision):
        # TODO: Use a config-based url for the base url below.
        base_url = 'https://deckhand/api/v1.0/%s/%s'
        return base_url % (self._collection_name, revision.get('id'))
