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

import copy

from deckhand.engine import revision_diff
from deckhand import factories
from deckhand.tests.unit.db import base


class TestRevisionDeepDiffing(base.TestDbBase):

    def _test_data(self):
        return {
            'data': [{'users': ['usr1', 'usr2'], 'description': 'normal user'},
                     {'hostname': 'ubuntubox', 'ip': '192.168.0.1'},
                     {'project_name': 'test1', 'region_name': 'reg01'}],
            'schema': ['user', 'host', 'project'],
            'doc_name': ['user1', 'host1', 'project1'],
            'policy': 'cleartext'
        }

    def test_revision_deepdiff_no_diff(self):
        test_data = copy.deepcopy(self._test_data())
        data = copy.deepcopy(test_data['data'])
        (schema, doc_name, policy) = (
            test_data['schema'], test_data['doc_name'], test_data['policy'])
        expected = {}
        rdf1 = factories.RenderedDocumentFactory('bucket_1', 1)
        rdoc1 = rdf1.gen_test(schema, doc_name, policy, data, 3)
        # both the rendered doc are same.
        rdoc2 = copy.deepcopy(rdoc1)
        actual = revision_diff._diff_buckets(rdoc1, rdoc2)
        self.assertEqual(expected, actual)

    def test_revision_deepdiff_show_diff(self):
        test_data = copy.deepcopy(self._test_data())
        data = copy.deepcopy(test_data['data'])
        (schema, doc_name, policy) = (
            test_data['schema'], test_data['doc_name'], test_data['policy'])
        expected_changed_doc = [(
            'deckhand/user/v1', 'user1'), ('deckhand/project/v1', 'project1')]
        rdf1 = factories.RenderedDocumentFactory('bucket_1', 1)
        rdoc1 = rdf1.gen_test(schema, doc_name, policy, data, 3)
        rdf2 = factories.RenderedDocumentFactory('bucket_1', 2)
        # change data
        data[0]['users'].append('usr3')
        data[2]['project_name'] = "test2"
        rdoc2 = rdf2.gen_test(schema, doc_name, policy, data, 3)
        actual = revision_diff._diff_buckets(rdoc1, rdoc2)
        # verify change document count
        self.assertEqual(2, actual['document_changed']['count'])
        # verify type of document changed
        expected_changed_doc = ["('deckhand/user/v1', 'user1')",
                                "('deckhand/project/v1', 'project1')"]
        actual_data = actual['document_changed']['details']
        actual_changed_doc = [k for k, v in actual_data.items()]
        self.assertEqual(
            [], list(set(expected_changed_doc) - set(actual_changed_doc)))

    def test_revision_deepdiff_doc_added(self):
        test_data = copy.deepcopy(self._test_data())
        data = copy.deepcopy(test_data['data'])
        (schema, doc_name, policy) = (
            test_data['schema'], test_data['doc_name'], test_data['policy'])
        expected_added_doc = [('deckhand/application/v1', 'application1')]
        rdf1 = factories.RenderedDocumentFactory('bucket_1', 1)
        rdoc1 = rdf1.gen_test(schema, doc_name, policy, data, 3)
        rdf2 = factories.RenderedDocumentFactory('bucket_1', 2)
        # add new document
        data.append({"application": "mysql", "port": "3306"})
        schema.append("application")
        doc_name.append("application1")
        rdoc2 = rdf2.gen_test(schema, doc_name, policy, data, 4)
        actual = revision_diff._diff_buckets(rdoc1, rdoc2)
        # verify added document count
        self.assertEqual(1, actual['document_added']['count'])
        # verify type of document added
        actual_added_doc = [d for d in actual['document_added']['details']]
        self.assertEqual(
            [], list(set(expected_added_doc) - set(actual_added_doc)))

    def test_revision_deepdiff_doc_deleted(self):
        test_data = copy.deepcopy(self._test_data())
        data = copy.deepcopy(test_data['data'])
        (schema, doc_name, policy) = (
            test_data['schema'], test_data['doc_name'], test_data['policy'])
        rdf1 = factories.RenderedDocumentFactory('bucket_1', 1)
        rdoc1 = rdf1.gen_test(schema, doc_name, policy, data, 3)
        rdf2 = factories.RenderedDocumentFactory('bucket_1', 2)
        # delete a document
        del data[2]
        del schema[2]
        del doc_name[2]
        rdoc2 = rdf2.gen_test(schema, doc_name, policy, data, 2)
        actual = revision_diff._diff_buckets(rdoc1, rdoc2)
        # verify deleted document count
        self.assertEqual(1, actual['document_deleted']['count'])
        # verify type of document deleted
        expected_deleted_doc = [('deckhand/project/v1', 'project1')]
        actual_deleted_doc = [d for d in actual['document_deleted']['details']]
        self.assertEqual(
            [], list(set(expected_deleted_doc) - set(actual_deleted_doc)))

    def test_revision_deepdiff_hide_password_diff(self):
        test_data = copy.deepcopy(self._test_data())
        data = copy.deepcopy(test_data['data'])
        (schema, doc_name, policy) = (
            test_data['schema'], test_data['doc_name'], test_data['policy'])
        rdf1 = factories.RenderedDocumentFactory('bucket_1', 1)
        # rdoc1: add encrypt type document
        (dt1, sc, do, po) = ([{"password": "ABC123"}], [
                             'node_password'], ['node1'], 'encrypted')
        rdf1.gen_test(sc, do, po, dt1)
        rdoc1 = rdf1.gen_test(schema, doc_name, policy, data, 3)
        rdf2 = factories.RenderedDocumentFactory('bucket_1', 2)
        # change password
        dt2 = [{"password": "xyz123"}]
        rdf2.gen_test(sc, do, po, dt2)
        rdoc2 = rdf2.gen_test(schema, doc_name, policy, data, 3)
        actual = revision_diff._diff_buckets(rdoc1, rdoc2)
        # verify change document count
        self.assertEqual(1, actual['document_changed']['count'])
        # verify type of document changed
        expected_changed_doc = ["('deckhand/node_password/v1', 'node1')"]
        actual_data = actual['document_changed']['details']
        actual_changed_doc = [k for k, v in actual_data.items()]
        self.assertEqual(
            [], list(set(expected_changed_doc) - set(actual_changed_doc)))
        # Ensure no password show in diff
        self.assertTrue(
            actual_data[expected_changed_doc[0]]['data_changed']['encrypted'])
