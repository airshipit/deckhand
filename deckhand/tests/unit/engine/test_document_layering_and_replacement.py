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

import inspect
import itertools
import os
import yaml

from deckhand.tests.unit.engine import test_document_layering

REPLACEMENT_3_TIER_SAMPLE = list(yaml.safe_load_all(inspect.cleandoc(
    """
    ---
    schema: deckhand/LayeringPolicy/v1
    metadata:
      schema: metadata/Control/v1
      name: layering-policy
      storagePolicy: cleartext
    data:
      layerOrder:
        - global
        - region
        - site
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: nova-global
      storagePolicy: cleartext
      labels:
        name: nova-global
        component: nova
      layeringDefinition:
        abstract: false
        layer: global
    data:
      values:
        pod:
          replicas:
            server: 16
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: nova
      storagePolicy: cleartext
      labels:
        name: nova-5ec
        component: nova
      layeringDefinition:
        abstract: false
        layer: region
        parentSelector:
          name: nova-global
        actions:
          - method: merge
            path: .
    data: {}
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      replacement: true
      storagePolicy: cleartext
      name: nova
      layeringDefinition:
        abstract: false
        layer: site
        parentSelector:
          name: nova-5ec
        actions:
          - method: merge
            path: .
    data:
      values:
        pod:
          replicas:
            api_metadata: 16
            placement: 2
            osapi: 16
            conductor: 16
            consoleauth: 2
            scheduler: 2
            novncproxy: 2
    """)))


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
  storagePolicy: cleartext
data:
  layerOrder:
    - global
    - site
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  storagePolicy: cleartext
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
  storagePolicy: cleartext
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
  storagePolicy: cleartext
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
        # Try different permutations of document orders for good measure.
        for documents in list(itertools.permutations(self.documents))[:10]:
            self._test_layering(
                documents, site_expected=site_expected,
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
  storagePolicy: cleartext
data:
  layerOrder:
    - global
    - site
---
schema: aic/Versions/v1
metadata:
  schema: metadata/Document/v1
  name: a
  storagePolicy: cleartext
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
  storagePolicy: cleartext
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
  storagePolicy: cleartext
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
  storagePolicy: cleartext
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

    def test_replacement_document_receives_substitution(self):
        """Verifies that the parent-replacement receives substitution data
        prior to the child-replacement layering with it, which in turn is
        done prior to any other document attempting to substitute from or
        layer with the child-replacement (which replaces its parent).
        """
        test_path = os.path.join(
            os.getcwd(), 'deckhand', 'tests', 'functional', 'gabbits',
            'resources', 'replacement.yaml')
        with open(test_path) as f:
            self.documents = list(yaml.safe_load_all(f))

        site_expected = [
            "CERTIFICATE DATA\n",
            "KEY DATA\n",
            {
                'chart': {
                    'details': {'data': 'bar'},
                    'values': {
                        'tls': {
                            'certificate': 'CERTIFICATE DATA\n',
                            'key': 'KEY DATA\n'
                        }
                    }
                }
            }
        ]

        self._test_layering(self.documents, site_expected=site_expected,
                            region_expected=None)

        # Try different permutations of document orders for good measure.
        for documents in list(itertools.permutations(self.documents))[:10]:
            self._test_layering(
                documents, site_expected=site_expected,
                region_expected=None)

    def test_multi_layer_replacement(self):
        """Validate the following scenario:

        * Global document called nova-global
        * Region document called nova (layers with nova-global)
        * Site document (replaces region document)
        """

        site_expected = [
            {
                "values": {
                    "pod": {
                        "replicas": {
                            "api_metadata": 16,
                            "placement": 2,
                            "osapi": 16,
                            "conductor": 16,
                            "consoleauth": 2,
                            "scheduler": 2,
                            "novncproxy": 2,
                            "server": 16
                        }
                    }
                }
            }
        ]
        global_expected = [
            {
                "values": {
                    "pod": {
                        "replicas": {
                            "server": 16
                        }
                    }
                }
            }
        ]
        self._test_layering(REPLACEMENT_3_TIER_SAMPLE,
                            site_expected=site_expected,
                            region_expected=None,
                            global_expected=global_expected)

    def test_multi_layer_replacement_with_intermediate_replacement(self):
        """Validate the following scenario:

        * Global document called nova-replace
        * Region document called nova-replace (layers with nova-replace and
          replaces it)
        * Site document (layers with region document)
        """

        replacement_sample = list(REPLACEMENT_3_TIER_SAMPLE)
        replacement_sample[1]['metadata']['name'] = 'nova-replace'
        replacement_sample[2]['metadata']['name'] = 'nova-replace'
        replacement_sample[2]['metadata']['replacement'] = True
        replacement_sample[3]['metadata']['replacement'] = False

        site_expected = [
            {
                "values": {
                    "pod": {
                        "replicas": {
                            "api_metadata": 16,
                            "placement": 2,
                            "osapi": 16,
                            "conductor": 16,
                            "consoleauth": 2,
                            "scheduler": 2,
                            "novncproxy": 2,
                            "server": 16
                        }
                    }
                }
            }
        ]
        region_expected = [
            {
                "values": {
                    "pod": {
                        "replicas": {
                            "server": 16
                        }
                    }
                }
            }
        ]
        self._test_layering(replacement_sample,
                            site_expected=site_expected,
                            region_expected=region_expected,
                            global_expected=None)
