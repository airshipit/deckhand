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

import yaml

import mock

from deckhand.control import revision_documents
from deckhand.engine import secrets_manager
from deckhand import errors
from deckhand import factories
from deckhand.tests.unit.control import base as test_base
from deckhand import types


class TestRenderedDocumentsController(test_base.BaseControllerTest):

    def test_list_rendered_documents_exclude_abstract_documents(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create 2 docs: one concrete, one abstract.
        documents_factory = factories.DocumentFactory(2, [1, 1])
        payload = documents_factory.gen_test({
            '_SITE_ACTIONS_1_': {
                'actions': [{'method': 'merge', 'path': '.'}]
            }
        }, global_abstract=False)
        concrete_doc = payload[1]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the concrete document is returned, but not the abstract
        # one.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        rendered_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(2, len(rendered_documents))
        rendered_documents = list(filter(
            lambda x: not x['schema'].startswith(types.LAYERING_POLICY_SCHEMA),
            rendered_documents))

        is_abstract = rendered_documents[-1]['metadata']['layeringDefinition'][
            'abstract']
        self.assertFalse(is_abstract)
        for key, value in concrete_doc.items():
            if isinstance(value, dict):
                self.assertDictContainsSubset(value,
                                              rendered_documents[-1][key])
            else:
                self.assertEqual(value, rendered_documents[-1][key])

    def test_list_rendered_documents_exclude_deleted_documents(self):
        """Verifies that documents from previous revisions that have been
        deleted are excluded from the current revision.

        Put x in bucket a -> revision 1. Put y in bucket a -> revision 2.
        Verify that only y is returned for revision 2.
        """
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # PUT a bunch of documents, include a layeringPolicy.
        documents_factory = factories.DocumentFactory(1, [1])
        payload = documents_factory.gen_test({}, global_abstract=False)
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)

        # PUT new document (exclude original documents from this payload).
        payload = documents_factory.gen_test({}, global_abstract=False)
        new_name = payload[1]['metadata']['name']
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all([payload[1]]))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that only the document with `new_name` is returned. (The
        # layeringPolicy) is omitted from the response even though it still
        # exists.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        rendered_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(2, len(rendered_documents))
        rendered_documents = list(filter(
            lambda x: not x['schema'].startswith(types.LAYERING_POLICY_SCHEMA),
            rendered_documents))

        self.assertEqual(new_name, rendered_documents[0]['metadata']['name'])
        self.assertEqual(2, rendered_documents[0]['status']['revision'])

    def test_list_rendered_documents_multiple_buckets(self):
        """Validates that only the documents from the most recent revision
        for each bucket in the DB are used for layering.
        """
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        bucket_names = ['first', 'first', 'second', 'second']

        # Create 2 documents for each revision. (1 `LayeringPolicy` is created
        # during the very 1st revision). Total = 9.
        for x in range(4):
            bucket_name = bucket_names[x]
            documents_factory = factories.DocumentFactory(2, [1, 1])
            payload = documents_factory.gen_test({
                '_SITE_ACTIONS_1_': {
                    'actions': [{'method': 'merge', 'path': '.'}]
                }
            }, global_abstract=False, site_abstract=False)
            # Fix up the labels so that each document has a unique parent to
            # avoid layering errors.
            payload[-2]['metadata']['labels'] = {
                'global': bucket_name
            }
            payload[-1]['metadata']['layeringDefinition']['parentSelector'] = {
                'global': bucket_name
            }

            if x > 0:
                payload = payload[1:]
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/%s/documents' % bucket_name,
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
            self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Although 9 documents have been created, 4 of those documents are
        # stale: they were created in older revisions, so expect 5 documents.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)

        documents = list(yaml.safe_load_all(resp.text))
        documents = sorted(documents, key=lambda x: x['status']['bucket'])

        # Validate that the LayeringPolicy was returned, then remove it
        # from documents to validate the rest of them.
        layering_policies = [
            d for d in documents
            if d['schema'].startswith(types.LAYERING_POLICY_SCHEMA)
        ]
        self.assertEqual(1, len(layering_policies))
        documents.remove(layering_policies[0])

        first_revision_ids = [d['status']['revision'] for d in documents
                              if d['status']['bucket'] == 'first']
        second_revision_ids = [d['status']['revision'] for d in documents
                               if d['status']['bucket'] == 'second']

        # Validate correct number of documents, the revision and bucket for
        # each document.
        self.assertEqual(4, len(documents))
        self.assertEqual(['first', 'first', 'second', 'second'],
                         [d['status']['bucket'] for d in documents])
        self.assertEqual(2, len(first_revision_ids))
        self.assertEqual(2, len(second_revision_ids))
        self.assertEqual([2, 2], first_revision_ids)
        self.assertEqual([4, 4], second_revision_ids)


class TestRenderedDocumentsControllerNegative(
        test_base.BaseControllerTest):

    def test_rendered_documents_fail_schema_validation(self):
        """Validates that when fully rendered documents fail schema validation,
        the controller raises a 500 Internal Server Error.
        """
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        documents_factory = factories.DocumentFactory(1, [1])
        payload = documents_factory.gen_test({})
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        with mock.patch.object(
                revision_documents, 'document_validation',
                autospec=True) as m_doc_validation:
            (m_doc_validation.DocumentValidation.return_value
                .validate_all.side_effect) = errors.InvalidDocumentFormat
            resp = self.app.simulate_get(
                '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
                headers={'Content-Type': 'application/x-yaml'})

        # Verify that a 500 Internal Server Error is thrown following failed
        # schema validation.
        self.assertEqual(500, resp.status_code)


class TestRenderedDocumentsControllerNegativeRBAC(
        test_base.BaseControllerTest):
    """Test suite for validating negative RBAC scenarios for rendered documents
    controller.
    """

    def test_list_cleartext_rendered_documents_insufficient_permissions(self):
        rules = {'deckhand:list_cleartext_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        documents_factory = factories.DocumentFactory(1, [1])
        payload = [documents_factory.gen_test({})[0]]
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(403, resp.status_code)

    def test_list_encrypted_rendered_documents_insufficient_permissions(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': 'rule:admin_api',
                 'deckhand:create_cleartext_documents': '@',
                 'deckhand:create_encrypted_documents': '@'}
        self.policy.set_rules(rules)

        # Create a document for a bucket.
        documents_factory = factories.DocumentFactory(1, [1])
        layering_policy = documents_factory.gen_test({})[0]
        secrets_factory = factories.DocumentSecretFactory()
        encrypted_document = secrets_factory.gen_test('Certificate',
                                                      'encrypted')
        payload = [layering_policy, encrypted_document]

        with mock.patch.object(secrets_manager, 'SecretsManager',
                               autospec=True) as mock_secrets_mgr:
            mock_secrets_mgr.create.return_value = payload[0]['data']
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/mop/documents',
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that the created document was not returned.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'},
            params={'schema': encrypted_document['schema']})
        self.assertEqual(200, resp.status_code)
        self.assertEmpty(list(yaml.safe_load_all(resp.text)))


class TestRenderedDocumentsControllerSorting(test_base.BaseControllerTest):

    def test_rendered_documents_sorting_metadata_name(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(2, [1, 1])
        documents = documents_factory.gen_test({
            '_SITE_ACTIONS_1_': {
                'actions': [{'method': 'merge', 'path': '.'}]
            }
        }, global_abstract=False, site_abstract=False)
        expected_names = ['bar', 'baz', 'foo']
        for idx in range(len(documents)):
            documents[idx]['metadata']['name'] = expected_names[idx]

        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(documents))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Test ascending order.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            params={'sort': 'metadata.name'}, params_csv=False,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(3, len(retrieved_documents))
        self.assertEqual(expected_names,
                         [d['metadata']['name'] for d in retrieved_documents])

        # Test descending order.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            params={'sort': 'metadata.name', 'order': 'desc'},
            params_csv=False, headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        retrieved_documents = list(yaml.safe_load_all(resp.text))

        self.assertEqual(3, len(retrieved_documents))
        self.assertEqual(list(reversed(expected_names)),
                         [d['metadata']['name'] for d in retrieved_documents])
