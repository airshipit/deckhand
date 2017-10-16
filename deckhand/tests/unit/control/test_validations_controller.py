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

import copy
import yaml

from oslo_config import cfg

from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.control import base as test_base
from deckhand import types

CONF = cfg.CONF


VALIDATION_RESULT = """
---
status: failure
errors:
  - documents:
      - schema: promenade/Node/v1
        name: node-document-name
      - schema: promenade/Masters/v1
        name: kubernetes-masters
    message: Node has master role, but not included in cluster masters list.
validator:
  name: promenade
  version: 1.1.2
"""

VALIDATION_RESULT_ALT = """
---
status: success
errors:
  - documents:
      - schema: promenade/Slaves/v1
        name: kubernetes-slaves
    message: No slave nodes found.
validator:
  name: promenade
  version: 1.1.2
"""


class TestValidationsController(test_base.BaseControllerTest):
    """Test suite for validating positive scenarios for bucket controller."""

    def _create_revision(self, payload=None):
        if not payload:
            documents_factory = factories.DocumentFactory(2, [1, 1])
            payload = documents_factory.gen_test({})
        resp = self.app.simulate_put('/api/v1.0/bucket/mop/documents',
                                     body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']
        return revision_id

    def _create_validation(self, revision_id, validation_name, policy):
        resp = self.app.simulate_post(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            body=policy)
        return resp

    def test_create_validation(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT)

        self.assertEqual(201, resp.status_code)
        expected_body = {
            'status': 'failure',
            'validator': {
                'name': 'promenade',
                'version': '1.1.2'
            }
        }
        self.assertEqual(expected_body, yaml.safe_load(resp.text))

    def test_list_validations(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)

        # Validate that the internal deckhand validation was created already.
        body = list(yaml.safe_load_all(resp.text))
        expected = {
            'count': 1,
            'results': [
                {
                    'status': 'success',
                    'name': types.DECKHAND_SCHEMA_VALIDATION
                }
            ]
        }
        self.assertEqual(1, len(body))
        self.assertEqual(expected, body[0])

        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Validate that, after creating a validation policy by an external
        # service, it is listed as well.
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {
                    'name': types.DECKHAND_SCHEMA_VALIDATION,
                    'status': 'success'
                },
                {
                    'name': validation_name,
                    'status': 'failure'
                }
            ]
        }
        self.assertEqual(expected_body, body)

    def test_list_validation_entries(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()

        # Validate that 3 entries (1 for each of the 3 documents created)
        # exists for
        # /api/v1.0/revisions/1/validations/deckhand-schema-validation
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION))
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 3,
            'results': [{'id': x, 'status': 'success'} for x in range(3)]
        }
        self.assertEqual(expected_body, body)

        # Add the result of a validation to a revision.
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT)

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name))
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'failure'}]
        }
        self.assertEqual(expected_body, body)

    def test_list_validation_entries_after_creating_validation(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()

        # Add the result of a validation to a revision.
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT)

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name))
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'failure'}]
        }
        self.assertEqual(expected_body, body)

        # Add the result of another validation to the same revision.
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT_ALT)

        # Validate that 2 entries now exist.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name))
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'id': 0, 'status': 'failure'}, {'id': 1, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_list_validation_entries_with_multiple_entries(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_RESULT)
        resp = resp = self._create_validation(revision_id, validation_name,
                                              VALIDATION_RESULT_ALT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name))
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'id': 0, 'status': 'failure'}, {'id': 1, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_show_validation_entry(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()
        validation_name = test_utils.rand_name('validation')
        resp = resp = self._create_validation(revision_id, validation_name,
                                              VALIDATION_RESULT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/0' % (revision_id,
                                                         validation_name))
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'name': validation_name,
            'status': 'failure',
            'createdAt': None,
            'expiresAfter': None,
            'errors': [
                {
                    'documents': [
                        {
                            'name': 'node-document-name',
                            'schema': 'promenade/Node/v1'
                        }, {
                            'name': 'kubernetes-masters',
                            'schema': 'promenade/Masters/v1'
                        }
                    ],
                    'message': 'Node has master role, but not included in '
                               'cluster masters list.'
                }
            ]
        }
        self.assertEqual(expected_body, body)

    def test_validation_with_registered_data_schema(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Register a `DataSchema` against which the test document will be
        # validated.
        data_schema_factory = factories.DataSchemaFactory()
        metadata_name = 'example/Doc/v1'
        schema_to_use = {
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'string'
                }
            },
            'required': ['a'],
            'additionalProperties': False
        }
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        revision_id = self._create_revision(payload=[data_schema])

        # Validate that the internal deckhand validation was created.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

        # Create the test document whose data section adheres to the
        # `DataSchema` above.
        doc_factory = factories.DocumentFactory(1, [1])
        doc_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'whatever'}}},
            global_abstract=False)[-1]
        doc_to_test['schema'] = 'example/Doc/v1'

        revision_id = self._create_revision(
            payload=[doc_to_test])

        # Validate that the validation was created and passed.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_validation_with_registered_data_schema_expect_failure(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Register a `DataSchema` against which the test document will be
        # validated.
        data_schema_factory = factories.DataSchemaFactory()
        metadata_name = 'example/foo/v1'
        schema_to_use = {
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'integer'  # Test doc will fail b/c of wrong type.
                }
            },
            'required': ['a']
        }
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        revision_id = self._create_revision(payload=[data_schema])

        # Validate that the internal deckhand validation was created.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

        # Create the test document that fails the validation due to the
        # schema defined by the `DataSchema` document.
        doc_factory = factories.DocumentFactory(1, [1])
        doc_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        doc_to_test['schema'] = 'example/foo/v1'
        doc_to_test['metadata']['name'] = 'test_doc'

        revision_id = self._create_revision(payload=[doc_to_test])

        # Validate that the validation was created and reports failure.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_validation_with_registered_data_schema_expect_mixed(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Register a `DataSchema` against which the test document will be
        # validated.
        data_schema_factory = factories.DataSchemaFactory()
        metadata_name = 'example/foo/v1'
        schema_to_use = {
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'integer'  # Test doc will fail b/c of wrong type.
                }
            },
            'required': ['a']
        }
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        revision_id = self._create_revision(payload=[data_schema])

        # Validate that the internal deckhand validation was created.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

        # Create a document that passes validation and another that fails it.
        doc_factory = factories.DocumentFactory(1, [1])
        fail_doc = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        fail_doc['schema'] = 'example/foo/v1'
        fail_doc['metadata']['name'] = 'test_doc'

        pass_doc = copy.deepcopy(fail_doc)
        pass_doc['data']['a'] = 5

        revision_id = self._create_revision(payload=[fail_doc, pass_doc])

        # Validate that the validation reports failure since `fail_doc`
        # should've failed validation.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id)
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_document_without_data_section_saves_but_fails_validation(self):
        """Validate that a document without the data section is saved to the
        database, but fails validation. This is a valid use case because a
        document in a bucket can be created without a data section, which
        depends on substitution from another document.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(1, [1])
        payload = documents_factory.gen_test({}, global_abstract=False)[-1]
        del payload['data']

        revision_id = self._create_revision(payload=[payload])

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION))
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'failure'}]
        }
        self.assertEqual(expected_body, body)
