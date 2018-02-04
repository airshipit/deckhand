# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

from deckhand.engine import layering
from deckhand import errors
from deckhand import factories
from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringWithSubstitutionNegative(
        test_document_layering.TestDocumentLayering):

    def test_layering_with_substitution_cycle_fails(self):
        """Validate that a substitution dependency cycle raises a critical
        failure.

        In the case below, the cycle exists between
        site-1 -> site-2 -> site-3 -> site-1
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_NAME_1_": "site-1",
            "_SITE_DATA_1_": {"data": {"c": "placeholder"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-3",
                    "path": "."
                }
            }],
            "_SITE_NAME_2_": "site-2",
            "_SITE_DATA_2_": {"data": {"d": "placeholder"}},
            "_SITE_ACTIONS_2_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_2_": [{
                "dest": {
                    "path": ".d"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-1",
                    "path": ".c"
                }
            }],
            "_SITE_NAME_3_": "site-3",
            "_SITE_DATA_3_": {"data": {"e": "placeholder"}},
            "_SITE_ACTIONS_3_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_3_": [{
                "dest": {
                    "path": ".e"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-2",
                    "path": ".d"
                }
            }]
        }
        doc_factory = factories.DocumentFactory(2, [1, 3])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        # Pass in the documents in reverse order to ensure that the dependency
        # chain by default is not linear and thus requires sorting.
        self.assertRaises(
            errors.SubstitutionDependencyCycle, layering.DocumentLayering,
            documents, substitution_sources=documents)

    def test_layering_with_substitution_self_reference_fails(self):
        """Validate that a substitution self-reference fails.

        In the case below, a self-reference or cycle exists for site-1 with
        itself.
        """
        mapping = {
            "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
            "_SITE_NAME_1_": "site-1",
            "_SITE_DATA_1_": {"data": {"c": "placeholder"}},
            "_SITE_ACTIONS_1_": {
                "actions": [{"method": "merge", "path": "."}]},
            "_SITE_SUBSTITUTIONS_1_": [{
                "dest": {
                    "path": ".c"
                },
                "src": {
                    "schema": "example/Kind/v1",
                    "name": "site-1",
                    "path": "."
                }
            }]
        }
        doc_factory = factories.DocumentFactory(2, [1, 1])
        documents = doc_factory.gen_test(mapping, site_abstract=False)

        # Pass in the documents in reverse order to ensure that the dependency
        # chain by default is not linear and thus requires sorting.
        self.assertRaises(
            errors.SubstitutionDependencyCycle, self._test_layering, documents,
            substitution_sources=documents)
