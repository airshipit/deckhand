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

import mock
from oslo_config import cfg

from deckhand.control import buckets
from deckhand.engine import document_validation
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.control import base as test_base
from deckhand import types

CONF = cfg.CONF


VALIDATION_FAILURE_RESULT = """
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

VALIDATION_SUCCESS_RESULT = """
---
status: success
errors: []
validator:
  name: promenade
  version: 1.1.2
"""


class ValidationsControllerBaseTest(test_base.BaseControllerTest):

    def _create_revision(self, payload=None):
        if not payload:
            documents_factory = factories.DocumentFactory(1, [1])
            payload = documents_factory.gen_test({})
            data_schema_factory = factories.DataSchemaFactory()
            data_schema = data_schema_factory.gen_test(
                payload[1]['schema'], data={})
            payload.append(data_schema)

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']
        return revision_id

    def _create_validation(self, revision_id, validation_name, policy):
        resp = self.app.simulate_post(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            headers={'Content-Type': 'application/x-yaml'}, body=policy)
        return resp

    def _monkey_patch_document_validation(self):
        """Workaround for testing complex validation scenarios by forcibly
        passing in `pre_validate=False`.
        """
        # TODO(fmontei): Remove this workaround by testing these more complex
        # scenarios against the rendered-documents endpoint instead (which
        # performs post-validation).
        original_document_validation = document_validation.DocumentValidation

        def monkey_patch(*args, **kwargs):
            return original_document_validation(*args, pre_validate=False)

        mock.patch.object(buckets.document_validation, 'DocumentValidation',
                          side_effect=monkey_patch, autospec=True).start()
        self.addCleanup(mock.patch.stopall)


class TestValidationsControllerPostValidate(ValidationsControllerBaseTest):
    """Test suite for validating positive scenarios for post-validations with
    Validations controller.
    """

    def setUp(self):
        super(TestValidationsControllerPostValidate, self).setUp()
        self._monkey_patch_document_validation()

    def test_create_validation(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_FAILURE_RESULT)

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
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
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
                                       VALIDATION_FAILURE_RESULT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
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
        body['results'] = sorted(body['results'], key=lambda x: x['name'])
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
                revision_id, types.DECKHAND_SCHEMA_VALIDATION),
            headers={'Content-Type': 'application/x-yaml'})
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
                                       VALIDATION_FAILURE_RESULT)

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            headers={'Content-Type': 'application/x-yaml'})
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
                                       VALIDATION_FAILURE_RESULT)

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'failure'}]
        }
        self.assertEqual(expected_body, body)

        # Add the result of another validation to the same revision.
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_SUCCESS_RESULT)

        # Validate that 2 entries now exist.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            headers={'Content-Type': 'application/x-yaml'})
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
        self._create_validation(revision_id, validation_name,
                                VALIDATION_FAILURE_RESULT)
        self._create_validation(revision_id, validation_name,
                                VALIDATION_SUCCESS_RESULT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (revision_id,
                                                       validation_name),
            headers={'Content-Type': 'application/x-yaml'})
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
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_FAILURE_RESULT)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/0' % (revision_id,
                                                         validation_name),
            headers={'Content-Type': 'application/x-yaml'})
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

    def test_show_nonexistent_validation_entry_returns_404(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        revision_id = self._create_revision()
        validation_name = test_utils.rand_name('validation')
        resp = self._create_validation(revision_id, validation_name,
                                       VALIDATION_FAILURE_RESULT)
        self.assertEqual(201, resp.status_code)
        expected_error = ('The requested validation entry 5 was not found for '
                          'validation name %s and revision ID %d.' % (
                              validation_name, revision_id))

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/5' % (revision_id,
                                                         validation_name),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(404, resp.status_code)
        self.assertEqual(expected_error, yaml.safe_load(resp.text)['message'])

    def test_validation_with_registered_data_schema(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
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

        # Create the test document whose data section adheres to the
        # `DataSchema` above.
        doc_factory = factories.DocumentFactory(1, [1])
        doc_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'whatever'}}},
            global_abstract=False)[-1]
        doc_to_test['schema'] = 'example/Doc/v1'

        revision_id = self._create_revision(payload=[doc_to_test, data_schema])

        # Validate that the validation was created and succeeded.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_validation_data_schema_different_revision_expect_failure(self):
        """Validates that creating a ``DataSchema`` in one revision and then
        creating a document in another revision that relies on the previously
        created ``DataSchema`` results in an expected failure.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@',
                 'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
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
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
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
        docs_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)
        docs_to_test[1]['schema'] = 'example/foo/v1'
        docs_to_test[1]['metadata']['name'] = 'test_doc'

        revision_id = self._create_revision(
            payload=docs_to_test + [data_schema])

        # Validate that the validation was created and reports failure.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

        # Validate that the validation was created and reports failure.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(400, resp.status_code)

    def test_validation_data_schema_same_revision_expect_failure(self):
        """Validates that creating a ``DataSchema`` alongside a document
        that relies on it in the same revision results in an expected failure.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
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

        # Create the test document that fails the validation due to the
        # schema defined by the `DataSchema` document.
        doc_factory = factories.DocumentFactory(1, [1])
        doc_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        doc_to_test['schema'] = 'example/foo/v1'
        doc_to_test['metadata']['name'] = 'test_doc'

        revision_id = self._create_revision(payload=[doc_to_test, data_schema])

        # Validate that the validation was created and reports failure.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_validation_with_registered_data_schema_expect_multi_failure(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
        # validated.
        data_schema_factory = factories.DataSchemaFactory()
        metadata_name = 'example/foo/v1'
        schema_to_use = {
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'integer'  # Test doc will fail b/c of wrong type.
                },
                'b': {
                    'type': 'string'
                }
            },
            'required': ['a', 'b']
        }
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        # Failure #1: Provide wrong type for property "a".
        # Failure #2: Don't include required property "b".
        doc_factory = factories.DocumentFactory(1, [1])
        doc_to_test = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        doc_to_test['schema'] = 'example/foo/v1'
        doc_to_test['metadata']['name'] = 'test_doc'

        revision_id = self._create_revision(payload=[doc_to_test, data_schema])

        # Validate that the validation was created and reports failure.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

        # Validate that both expected errors are present for validation.
        expected_errors = [{
            'error_section': {
                'data': {'a': 'fail'},
                'metadata': {'labels': {'global': 'global1'},
                             'layeringDefinition': {'abstract': False,
                                                    'layer': 'global'},
                             'name': doc_to_test['metadata']['name'],
                             'schema': doc_to_test['metadata']['schema']},
                'schema': doc_to_test['schema']
            },
            'name': 'test_doc',
            'path': '.data',
            'schema': 'example/foo/v1',
            'message': "'b' is a required property",
            'validation_schema': schema_to_use,
            'schema_path': '.required'
        }, {
            'error_section': {'a': 'fail'},
            'name': 'test_doc',
            'path': '.data.a',
            'schema': 'example/foo/v1',
            'message': "'fail' is not of type 'integer'",
            'validation_schema': schema_to_use,
            'schema_path': '.properties.a.type'
        }]
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/0' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)

        self.assertEqual('failure', body['status'])
        self.assertEqual(sorted(expected_errors, key=lambda x: x['path']),
                         sorted(body['errors'], key=lambda x: x['path']))

    def test_validation_with_registered_data_schema_expect_mixed(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
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
        expected_errors = [{
            'error_section': {'a': 'fail'},
            'name': 'test_doc',
            'path': '.data.a',
            'schema': 'example/foo/v1',
            'message': "'fail' is not of type 'integer'",
            'validation_schema': schema_to_use,
            'schema_path': '.properties.a.type'
        }]
        data_schema = data_schema_factory.gen_test(
            metadata_name, data=schema_to_use)

        # Create a document that passes validation and another that fails it.
        doc_factory = factories.DocumentFactory(1, [1])
        fail_doc = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        fail_doc['schema'] = 'example/foo/v1'
        fail_doc['metadata']['name'] = 'test_doc'

        pass_doc = copy.deepcopy(fail_doc)
        pass_doc['data']['a'] = 5

        revision_id = self._create_revision(
            payload=[fail_doc, pass_doc, data_schema])

        # Validate that the validation reports failure since `fail_doc`
        # should've failed validation.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'failure'}
            ]
        }
        self.assertEqual(expected_body, body)

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 3,
            'results': [{'id': 0, 'status': 'failure'},  # fail_doc failed.
                        {'id': 1, 'status': 'success'},  # DataSchema passed.
                        {'id': 2, 'status': 'success'}]  # pass_doc succeeded.
        }
        self.assertEqual(expected_body, body)

        # Validate that fail_doc validation failed for the expected reason.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/0' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_errors = [{
            'error_section': {'a': 'fail'},
            'name': 'test_doc',
            'path': '.data.a',
            'schema': 'example/foo/v1',
            'message': "'fail' is not of type 'integer'",
            'validation_schema': schema_to_use,
            'schema_path': '.properties.a.type'
        }]

        self.assertIn('errors', body)
        self.assertEqual(expected_errors, body['errors'])

    def test_document_without_data_section_ingested(self):
        """Validate that a document without the data section is ingested
        successfully.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(1, [1])
        document = documents_factory.gen_test({}, global_abstract=False)[-1]
        del document['data']

        data_schema_factory = factories.DataSchemaFactory()
        data_schema = data_schema_factory.gen_test(document['schema'], {})

        revision_id = self._create_revision(payload=[document, data_schema])

        # Validate that the entry is present.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, types.DECKHAND_SCHEMA_VALIDATION),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)

        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [{'id': 0, 'status': 'success'},  # Document.
                        {'id': 1, 'status': 'success'}]  # DataSchema.
        }
        self.assertEqual(expected_body, body)

    def test_validation_only_new_data_schema_registered(self):
        """Validate whether newly created DataSchemas replace old DataSchemas
        when it comes to validation.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create 2 DataSchemas that will fail if they're used. These shouldn't
        # be used for validation.
        data_schema_factory = factories.DataSchemaFactory()
        metadata_names = ['exampleA/Doc/v1', 'exampleB/Doc/v1']
        schemas_to_use = [{
            '$schema': 'http://json-schema.org/schema#',
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'integer'
                }
            },
            'required': ['a'],
            'additionalProperties': False
        }] * 2
        old_data_schemas = [
            data_schema_factory.gen_test(
                metadata_names[i], data=schemas_to_use[i])
            for i in range(2)
        ]
        # Save the DataSchemas in the first revision.
        revision_id = self._create_revision(payload=old_data_schemas)

        # Create 2 DataSchemas that will pass if they're used. These should
        # be used for validation.
        for schema_to_use in schemas_to_use:
            schema_to_use['properties']['a']['type'] = 'string'
        new_data_schemas = [
            data_schema_factory.gen_test(
                metadata_names[i], data=schemas_to_use[i])
            for i in range(2)
        ]
        doc_factory = factories.DocumentFactory(1, [1])
        example1_doc = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'whatever'}}},
            global_abstract=False)[-1]
        example1_doc['schema'] = metadata_names[0]
        example2_doc = copy.deepcopy(example1_doc)
        example2_doc['schema'] = metadata_names[1]
        # Save the documents that will be validated alongside the DataSchemas
        # that will be used to validate them.
        revision_id = self._create_revision(
            payload=[example1_doc, example2_doc] + new_data_schemas)

        # Validate that the validation was created and succeeded: This means
        # that the new DataSchemas were used, not the old ones.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)


class TestValidationsControllerWithValidationPolicy(
        ValidationsControllerBaseTest):

    def setUp(self):
        super(TestValidationsControllerWithValidationPolicy, self).setUp()
        self._monkey_patch_document_validation()

    def test_validation_with_validation_policy_success(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create a `ValidationPolicy` which is used to check whether a revision
        # passed all the validations.
        validation_policy = yaml.safe_load("""
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: site-deploy-ready
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: deckhand-schema-validation
...
""")
        revision_id = self._create_revision(payload=[validation_policy])

        # Validate that the validation was created and reports success.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': 'deckhand-schema-validation', 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)

    def test_with_validation_policy_external_validation(self):
        """Validate that a ValidationPolicy with an externally registered
        validation that is successful passes.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create a `ValidationPolicy` which expects two validations.
        validation_policy = yaml.safe_load("""
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: site-deploy-ready
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: deckhand-schema-validation
    - name: promenade-schema-validation
...
""")
        revision_id = self._create_revision(payload=[validation_policy])

        # Create the external validation for "promenade-schema-validation".
        resp = self._create_validation(
            revision_id, 'promenade-schema-validation',
            VALIDATION_SUCCESS_RESULT)
        self.assertEqual(201, resp.status_code)

        # Validate that the validation was created and reports success.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'name': 'deckhand-schema-validation', 'status': 'success'},
                {'name': 'promenade-schema-validation', 'status': 'success'}
            ]
        }
        body['results'] = sorted(body['results'], key=lambda x: x['name'])
        self.assertEqual(expected_body, body)

    def test_with_multiple_validation_policy_external_validation(self):
        """Validate that two ValidationPolicy documents, one that references
        the internal deckhand-schema-validation, and the other which requires
        an externally registered validation, produces a successful validation
        result.
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create two `ValidationPolicy` documents.
        validation_policies = yaml.safe_load_all("""
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: vp-1
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: deckhand-schema-validation
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: vp-2
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: promenade-schema-validation
...
""")
        revision_id = self._create_revision(payload=validation_policies)

        # Create the external validation for "promenade-schema-validation".
        resp = self._create_validation(
            revision_id, 'promenade-schema-validation',
            VALIDATION_SUCCESS_RESULT)
        self.assertEqual(201, resp.status_code)

        # Validate that the validation was created and reports success.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'name': 'deckhand-schema-validation', 'status': 'success'},
                {'name': 'promenade-schema-validation', 'status': 'success'}
            ]
        }
        body['results'] = sorted(body['results'], key=lambda x: x['name'])
        self.assertEqual(expected_body, body)

    def test_with_validation_policy_missing_external_validation(self):
        """Validate that a ValidationPolicy with a missing externally
        registered validation that is listed under the validations for the
        ValidationPolicy defaults to "failure".
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        # Create a `ValidationPolicy` which expects two validations but do not
        # create the validation for "promenade-schema-validation".
        validation_policy = yaml.safe_load("""
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: site-deploy-ready
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: deckhand-schema-validation
    - name: promenade-schema-validation
...
""")
        revision_id = self._create_revision(payload=[validation_policy])

        # Validate that the validation was created and that the missing one
        # defaults to "failure".
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'name': 'deckhand-schema-validation', 'status': 'success'},
                {'name': 'promenade-schema-validation', 'status': 'failure'}
            ]
        }
        body['results'] = sorted(body['results'], key=lambda x: x['name'])
        self.assertEqual(expected_body, body)

        # Validate that 'promenade-schema-validation' is 'failure' even though
        # it was never externally registered.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, 'promenade-schema-validation'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'failure'}]
        }
        self.assertEqual(expected_body, body)

        # Validate information explaining why 'promenade-schema-validation'
        # failed is returned. Note that DH should be smart enough to say that
        # it was never registered externally, which is why it's 'failure'.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/0' % (
                revision_id, 'promenade-schema-validation'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)

        expected_msg = ('The result for this validation was never externally '
                        'registered so its status defaulted to "failure".')
        expected_body = {
            'name': 'promenade-schema-validation',
            'status': 'failure',
            'createdAt': None,
            'expiresAfter': None,
            'errors': [{'message': expected_msg}]
        }
        self.assertEqual(expected_body, body)

    def test_with_validation_policy_extra_external_validation(self):
        """Validate that a ValidationPolicy with extra externally registered
        validations that aren't listed under the validations for the
        ValidationPolicy defaults to "ignored [{original_status}]".
        """
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_validation': '@',
                 'deckhand:list_validations': '@',
                 'deckhand:show_validation': '@'}
        self.policy.set_rules(rules)

        # Create a `ValidationPolicy` with only 1 validation.
        validation_policy = yaml.safe_load("""
---
schema: deckhand/ValidationPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: site-deploy-ready
  layeringDefinition:
    abstract: true
data:
  validations:
    - name: deckhand-schema-validation
...
""")
        revision_id = self._create_revision(payload=[validation_policy])

        # Register an extra validation not in the ValidationPolicy.
        resp = self._create_validation(
            revision_id, 'promenade-schema-validation',
            VALIDATION_FAILURE_RESULT)
        self.assertEqual(201, resp.status_code)

        # Validate that the extra validation is ignored.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 2,
            'results': [
                {'name': 'deckhand-schema-validation', 'status': 'success'},
                {'name': 'promenade-schema-validation',
                 'status': 'ignored [failure]'}
            ]
        }
        body['results'] = sorted(body['results'], key=lambda x: x['name'])
        self.assertEqual(expected_body, body)

        # Validate that 'promenade-schema-validation' is 'ignored [failure]'
        # even though it was externally registered.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s' % (
                revision_id, 'promenade-schema-validation'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [{'id': 0, 'status': 'ignored [failure]'}]
        }
        self.assertEqual(expected_body, body)

        # Validate information explaining why 'promenade-schema-validation'
        # is ignored is returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations/%s/entries/0' % (
                revision_id, 'promenade-schema-validation'),
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)

        expected_msg = ('The result for this validation was externally '
                        'registered but has been ignored because it is not '
                        'found in the validations for ValidationPolicy [%s] '
                        '%s: %s.' % (validation_policy['schema'],
                                     validation_policy['metadata']['name'],
                                     types.DECKHAND_SCHEMA_VALIDATION))
        expected_errors = yaml.safe_load(VALIDATION_FAILURE_RESULT)['errors']
        expected_errors.append({'message': expected_msg})

        expected_body = {
            'name': 'promenade-schema-validation',
            'status': 'ignored [failure]',
            'createdAt': None,
            'expiresAfter': None,
            'errors': expected_errors
        }
        self.assertEqual(expected_body, body)


class TestValidationsControllerPreValidate(ValidationsControllerBaseTest):
    """Test suite for validating positive scenarios for pre-validations with
    Validations controller.
    """

    def test_pre_validate_flag_skips_registered_dataschema_validations(self):
        rules = {'deckhand:create_cleartext_documents': '@',
                 'deckhand:list_validations': '@'}
        self.policy.set_rules(rules)

        # Create a `DataSchema` against which the test document will be
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

        # Create a document that passes validation and another that fails it.
        doc_factory = factories.DocumentFactory(1, [1])
        fail_doc = doc_factory.gen_test(
            {'_GLOBAL_DATA_1_': {'data': {'a': 'fail'}}},
            global_abstract=False)[-1]
        fail_doc['schema'] = 'example/foo/v1'
        fail_doc['metadata']['name'] = 'test_doc'

        revision_id = self._create_revision(payload=[data_schema, fail_doc])

        # Validate that the validation reports success because `fail_doc`
        # isn't validated by the `DataSchema`.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/validations' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        body = yaml.safe_load(resp.text)
        expected_body = {
            'count': 1,
            'results': [
                {'name': types.DECKHAND_SCHEMA_VALIDATION, 'status': 'success'}
            ]
        }
        self.assertEqual(expected_body, body)
