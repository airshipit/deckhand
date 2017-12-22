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

from deckhand.control import buckets
from deckhand.control import revision_documents
from deckhand import errors
from deckhand import factories
from deckhand.tests import test_utils
from deckhand.tests.unit.control import base as test_base


class TestRenderedDocumentsController(test_base.BaseControllerTest):

    def test_list_rendered_documents_exclude_abstract_documents(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        # Create 2 docs: one concrete, one abstract.
        documents_factory = factories.DocumentFactory(2, [1, 1])
        payload = documents_factory.gen_test(
            {}, global_abstract=False, region_abstract=True)
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
        self.assertEqual(1, len(rendered_documents))
        is_abstract = rendered_documents[0]['metadata']['layeringDefinition'][
            'abstract']
        self.assertFalse(is_abstract)
        for key, value in concrete_doc.items():
            if isinstance(value, dict):
                self.assertDictContainsSubset(value,
                                              rendered_documents[0][key])
            else:
                self.assertEqual(value, rendered_documents[0][key])

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

        # Create 1st document.
        documents_factory = factories.DocumentFactory(1, [1])
        payload = documents_factory.gen_test({}, global_abstract=False)[1:]
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)

        # Create 2nd document (exclude 1st document in new payload).
        payload = documents_factory.gen_test({}, global_abstract=False)
        new_name = payload[-1]['metadata']['name']
        resp = self.app.simulate_put(
            '/api/v1.0/buckets/mop/documents',
            headers={'Content-Type': 'application/x-yaml'},
            body=yaml.safe_dump_all(payload))
        self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        # Verify that only the 2nd is returned for revision_id=2.
        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)

        rendered_documents = list(yaml.safe_load_all(resp.text))
        self.assertEqual(1, len(rendered_documents))
        self.assertEqual(new_name, rendered_documents[0]['metadata']['name'])
        self.assertEqual(2, rendered_documents[0]['status']['revision'])

    def test_list_rendered_documents_multiple_buckets(self):
        rules = {'deckhand:list_cleartext_documents': '@',
                 'deckhand:list_encrypted_documents': '@',
                 'deckhand:create_cleartext_documents': '@'}
        self.policy.set_rules(rules)

        documents_factory = factories.DocumentFactory(1, [1])

        for idx in range(2):
            payload = documents_factory.gen_test({})
            if idx == 0:
                # Pop off the first entry so that a conflicting layering
                # policy isn't created during the 1st iteration.
                payload.pop(0)
            resp = self.app.simulate_put(
                '/api/v1.0/buckets/%s/documents' % test_utils.rand_name(
                    'bucket'),
                headers={'Content-Type': 'application/x-yaml'},
                body=yaml.safe_dump_all(payload))
            self.assertEqual(200, resp.status_code)
        revision_id = list(yaml.safe_load_all(resp.text))[0]['status'][
            'revision']

        resp = self.app.simulate_get(
            '/api/v1.0/revisions/%s/rendered-documents' % revision_id,
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)


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

        with mock.patch.object(buckets.BucketsResource, 'secrets_mgr',
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
            headers={'Content-Type': 'application/x-yaml'})
        self.assertEqual(200, resp.status_code)
        self.assertEmpty(list(yaml.safe_load_all(resp.text)))
