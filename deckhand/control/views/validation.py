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

from deckhand.control import common


class ViewBuilder(common.ViewBuilder):
    """Model validation API responses as a python dictionary."""

    _collection_name = 'validations'

    def list(self, validations):
        return {
            'count': len(validations),
            'results': [
                {'name': v[0], 'status': v[1]} for v in validations
            ]
        }

    def detail(self, entries):
        results = []

        for idx, entry in enumerate(entries):
            formatted_entry = self.show_entry(entry)
            formatted_entry.setdefault('id', idx)
            results.append(formatted_entry)

        return {
            'count': len(results),
            'results': results
        }

    def list_entries(self, entries):
        results = []

        for idx, e in enumerate(entries):
            results.append({'status': e['status'], 'id': idx})

        return {
            'count': len(entries),
            'results': results
        }

    def show(self, validation):
        return {
            'status': validation.get('status'),
            'validator': validation.get('validator')
        }

    def show_entry(self, entry):
        return {
            'name': entry.get('name'),
            'status': entry.get('status'),
            'createdAt': entry.get('createdAt'),
            'expiresAfter': entry.get('expiresAfter'),
            'errors': entry.get('errors')
        }
