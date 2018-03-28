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

import itertools
import yaml

from deckhand.tests.unit.engine import test_document_layering


class TestDocumentLayeringWithReplacement(
        test_document_layering.TestDocumentLayering):

    def setUp(self):
        super(TestDocumentLayeringWithReplacement, self).setUp()
        self.documents = list(yaml.safe_load_all("""
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
    - site
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  labels:
    selector: foo
  layeringDefinition:
    abstract: False
    layer: global
data:
  conf:
    foo: default
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  labels:
    selector: baz
  replacement: true
  layeringDefinition:
    abstract: False
    layer: site
    parentSelector:
      selector: foo
    actions:
      - method: merge
        path: .
data:
  conf:
    bar: override
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: c
  layeringDefinition:
    abstract: False
    layer: global
  substitutions:
    - src:
        schema: aic/Versions/v1
        name: a
        path: .conf
      dest:
        path: .application.conf
data:
  application:
    conf: {}
...
"""))

    def test_basic_replacement(self):
        """Verify that the replacement document is the only one returned."""
        site_expected = [{"conf": {"foo": "default", "bar": "override"}}]
        global_expected = None

        self.documents = self.documents[:-1]

        self._test_layering(self.documents, site_expected,
                            global_expected=global_expected)

    def test_replacement_with_substitution_from_replacer(self):
        """Verify that using a replacement document as a substitution source
        works.
        """
        site_expected = [{"conf": {"foo": "default", "bar": "override"}}]
        global_expected = [
            {"application": {"conf": {"foo": "default", "bar": "override"}}}]
        # The replacer should be used as the source.
        self._test_layering(self.documents, site_expected,
                            global_expected=global_expected)
        # Attempt the same scenario but reverse the order of the documents,
        # which verifies that the replacer always takes priority.
        self._test_layering(self.documents, site_expected,
                            global_expected=global_expected)

    def test_replacement_with_layering_with_replacer(self):
        """Verify that replacement works alongside layering. This scenario
        involves a parent, a child that replaces its parent, and yet another
        child that layers with the replacement document.
        """
        self.documents = list(yaml.safe_load_all("""
---
schema: deckhand/LayeringPolicy/v1
metadata:
  schema: metadata/Control/v1
  name: layering-policy
data:
  layerOrder:
    - global
    - site
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  labels:
    selector: foo
  layeringDefinition:
    abstract: False
    layer: global
data:
  conf:
    foo: default
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  labels:
    selector: baz
  replacement: true
  layeringDefinition:
    abstract: False
    layer: site
    parentSelector:
      selector: foo
    actions:
      - method: merge
        path: .
data:
  conf:
    bar: override
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: b
  labels:
    selector: qux
  layeringDefinition:
    abstract: False
    layer: site
    parentSelector:
      selector: foo
    actions:
      - method: merge
        path: .
data:
  conf:
    baz: another
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: c
  layeringDefinition:
    abstract: False
    layer: global
  substitutions:
    - src:
        schema: aic/Versions/v1
        name: a
        path: .conf
      dest:
        path: .application.conf
data:
  application:
    conf: {}
...
"""))

        site_expected = [
            {"conf": {"foo": "default", "bar": "override"}},
            {"conf": {"foo": "default", "bar": "override", "baz": "another"}},
        ]
        global_expected = [
            {"application": {"conf": {"foo": "default", "bar": "override"}}}
        ]
        self._test_layering(self.documents, site_expected=site_expected,
                            global_expected=global_expected)

        # Try different permutations of document orders for good measure.
        for documents in list(itertools.permutations(self.documents))[:10]:
            self._test_layering(
                documents, site_expected=site_expected,
                global_expected=global_expected)
