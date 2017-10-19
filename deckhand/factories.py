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

import abc
import copy
import six

from oslo_log import log as logging

from deckhand.tests import test_utils
from deckhand import types

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class DeckhandFactory(object):
    # TODO(fmontei): Allow this to be overriden in ``__init__``.
    API_VERSION = '1.0'

    @abc.abstractmethod
    def gen(self, *args):
        """Generate an object for usage by the Deckhand `engine` module."""
        pass

    @abc.abstractmethod
    def gen_test(self, *args, **kwargs):
        """Generate an object with randomized values for a test."""
        pass


class DataSchemaFactory(DeckhandFactory):
    """Class for auto-generating ``DataSchema`` templates for testing."""

    DATA_SCHEMA_TEMPLATE = {
        "data": {
            "$schema": ""
        },
        "metadata": {
            "schema": "metadata/Control/v1",
            "name": "",
            "labels": {}
        },
        "schema": "deckhand/DataSchema/v1"
    }

    def __init__(self):
        """Constructor for ``DataSchemaFactory``.

        Returns a template whose YAML representation is of the form::

            ---
            schema: deckhand/DataSchema/v1
            metadata:
                schema: metadata/Control/v1
                name: promenade/Node/v1
                labels:
                    application: promenade
            data:
                $schema: http://blah
            ...
        """

    def gen(self):
        raise NotImplementedError()

    def gen_test(self, metadata_name, data, **metadata_labels):
        data_schema_template = copy.deepcopy(self.DATA_SCHEMA_TEMPLATE)

        data_schema_template['metadata']['name'] = metadata_name
        data_schema_template['metadata']['labels'] = metadata_labels
        data_schema_template['data'] = data

        return data_schema_template


class DocumentFactory(DeckhandFactory):
    """Class for auto-generating document templates for testing."""

    LAYERING_DEFINITION = {
        "data": {
            "layerOrder": []
        },
        "metadata": {
            "name": "placeholder",
            "schema": "metadata/Control/v%s" % DeckhandFactory.API_VERSION
        },
        "schema": "deckhand/LayeringPolicy/v%s" % DeckhandFactory.API_VERSION
    }

    LAYER_TEMPLATE = {
        "data": {},
        "metadata": {
            "labels": {"": ""},
            "layeringDefinition": {
                "abstract": False,
                "layer": "",
                "actions": []
            },
            "name": "",
            "schema": "metadata/Document/v%s" % DeckhandFactory.API_VERSION
        },
        "schema": "example/Kind/v1.0"
    }

    def __init__(self, num_layers, docs_per_layer):
        """Constructor for ``DocumentFactory``.

        Returns a template whose JSON representation is of the form::

            [{'data': {'layerOrder': ['global', 'region', 'site']},
              'metadata': {'name': 'layering-policy',
                           'schema': 'metadata/Control/v1'},
              'schema': 'deckhand/LayeringPolicy/v1'},
             {'data': {'a': 1, 'b': 2},
              'metadata': {'labels': {'global': 'global1'},
                           'layeringDefinition': {'abstract': True,
                                                  'actions': [],
                                                  'layer': 'global',
                                                  'parentSelector': ''},
                           'name': 'global1',
                           'schema': 'metadata/Document/v1'},
              'schema': 'example/Kind/v1'}
             ...
            ]

        :param num_layers: Total number of layers. Only supported values
            include 1, 2 or 3.
        :type num_layers: integer
        :param docs_per_layer: The number of documents to be included per
            layer. For example, if ``num_layers`` is 3, then ``docs_per_layer``
            can be (1, 1, 1) for 1 document for each layer or (1, 2, 3) for 1
            doc for the 1st layer, 2 docs for the 2nd layer, and 3 docs for the
            3rd layer.
        :type docs_per_layer: tuple, list
        :raises TypeError: If ``docs_per_layer`` is not the right type.
        :raises ValueError: If ``num_layers`` is not the right value or isn't
            compatible with ``docs_per_layer``.
        """
        # Set up the layering definition's layerOrder.
        if num_layers == 1:
            layer_order = ["global"]
        elif num_layers == 2:
            layer_order = ["global", "site"]
        elif num_layers == 3:
            layer_order = ["global", "region", "site"]
        else:
            raise ValueError("'num_layers' must be a value between 1 - 3.")
        self.layering_definition = copy.deepcopy(self.LAYERING_DEFINITION)
        self.layering_definition['metadata']['name'] = test_utils.rand_name(
            'layering-policy')
        self.layering_definition['data']['layerOrder'] = layer_order

        if not isinstance(docs_per_layer, (list, tuple)):
            raise TypeError("'docs_per_layer' must be a list or tuple "
                            "indicating the number of documents per layer.")
        elif not len(docs_per_layer) == num_layers:
            raise ValueError("The number of entries in 'docs_per_layer' must"
                             "be equal to the value of 'num_layers'.")

        for doc_count in docs_per_layer:
            if doc_count < 1:
                raise ValueError(
                    "Each entry in 'docs_per_layer' must be >= 1.")

        self.num_layers = num_layers
        self.docs_per_layer = docs_per_layer

    def gen(self):
        raise NotImplementedError()

    def gen_test(self, mapping, site_abstract=True, region_abstract=True,
                 global_abstract=True, site_parent_selectors=None):
        """Generate the document template.

        Generate the document template based on the arguments passed to
        the constructor and to this function.

        :param mapping: A list of dictionaries that specify the "data" and
            "actions" parameters for each document. A valid mapping is::

                mapping = {
                    "_GLOBAL_DATA_1_": {"data": {"a": {"x": 1, "y": 2}}},
                    "_SITE_DATA_1_": {"data": {"a": {"x": 7, "z": 3}, "b": 4}},
                    "_SITE_ACTIONS_1_": {
                        "actions": [{"method": "merge", "path": path}]}
                }

            Each key must be of the form "_{LAYER_NAME}_{KEY_NAME}_{N}_"
            where:

                - {LAYER_NAME} is the name of the layer ("global", "region",
                    "site")
                - {KEY_NAME} is either "DATA" or "ACTIONS"
                - {N} is the occurrence of the document based on the
                    values in ``docs_per_layer``. If ``docs_per_layer`` is
                    (1, 2) then _GLOBAL_DATA_1_, _SITE_DATA_1_, _SITE_DATA_2_,
                    _SITE_ACTIONS_1_ and _SITE_ACTIONS_2_ must be provided.
                    _GLOBAL_ACTIONS_{N}_ is ignored.

        :type mapping: dict
        :param site_abstract: Whether site layers are abstract/concrete.
        :type site_abstract: boolean
        :param region_abstract: Whether region layers are abstract/concrete.
        :type region_abstract: boolean
        :param global_abstract: Whether global layers are abstract/concrete.
        :type global_abstract: boolean
        :param site_parent_selectors: Override the default parent selector
            for each site. Assuming that ``docs_per_layer`` is (2, 2), for
            example, a valid value is::

                [{'global': 'global1'}, {'global': 'global2'}]

            If not specified, each site will default to the first parent.
        :type site_parent_selectors: list
        :returns: Rendered template of the form specified above.
        """
        rendered_template = [self.layering_definition]
        layer_order = rendered_template[0]['data']['layerOrder']

        for layer_idx in range(self.num_layers):
            for count in range(self.docs_per_layer[layer_idx]):
                layer_template = copy.deepcopy(self.LAYER_TEMPLATE)
                layer_name = layer_order[layer_idx]

                # Set name.
                layer_template = copy.deepcopy(layer_template)
                layer_template['metadata']['name'] = "%s%d" % (
                    layer_name, count + 1)

                # Set layer.
                layer_template['metadata']['layeringDefinition'][
                    'layer'] = layer_name

                # Set labels.
                layer_template['metadata']['labels'] = {layer_name: "%s%d" % (
                    layer_name, count + 1)}

                # Set parentSelector.
                if layer_name == 'site' and site_parent_selectors:
                    parent_selector = site_parent_selectors[count]
                    layer_template['metadata']['layeringDefinition'][
                        'parentSelector'] = parent_selector
                elif layer_idx > 0:
                    parent_selector = rendered_template[layer_idx][
                        'metadata']['labels']
                    layer_template['metadata']['layeringDefinition'][
                        'parentSelector'] = parent_selector

                # Set abstract.
                if layer_name == 'site':
                    layer_template['metadata']['layeringDefinition'][
                        'abstract'] = site_abstract
                if layer_name == 'region':
                    layer_template['metadata']['layeringDefinition'][
                        'abstract'] = region_abstract
                if layer_name == 'global':
                    layer_template['metadata']['layeringDefinition'][
                        'abstract'] = global_abstract

                # Set data and actions.
                data_key = "_%s_DATA_%d_" % (layer_name.upper(), count + 1)
                actions_key = "_%s_ACTIONS_%d_" % (
                    layer_name.upper(), count + 1)
                sub_key = "_%s_SUBSTITUTIONS_%d_" % (
                    layer_name.upper(), count + 1)

                try:
                    layer_template['data'] = mapping[data_key]['data']
                except KeyError as e:
                    LOG.debug('Could not map %s because it was not found in '
                              'the `mapping` dict.', e.args[0])
                    pass

                try:
                    layer_template['metadata']['layeringDefinition'][
                        'actions'] = mapping[actions_key]['actions']
                except KeyError as e:
                    LOG.debug('Could not map %s because it was not found in '
                              'the `mapping` dict.', e.args[0])
                    pass

                try:
                    layer_template['metadata']['substitutions'] = mapping[
                        sub_key]
                except KeyError as e:
                    LOG.debug('Could not map %s because it was not found in '
                              'the `mapping` dict.', e.args[0])
                    pass

                rendered_template.append(layer_template)

        return rendered_template


class DocumentSecretFactory(DeckhandFactory):
    """Class for auto-generating document secrets templates for testing.

    Returns formats that adhere to the following supported schemas:

      * deckhand/Certificate/v1
      * deckhand/CertificateKey/v1
      * deckhand/Passphrase/v1
    """

    DOCUMENT_SECRET_TEMPLATE = {
        "data": {
        },
        "metadata": {
            "schema": "metadata/Document/v1",
            "name": "application-api",
            "storagePolicy": ""
        },
        "schema": "deckhand/%s/v1"
    }

    def __init__(self):
        """Constructor for ``DocumentSecretFactory``.

        Returns a template whose YAML representation is of the form::

            ---
            schema: deckhand/Certificate/v1
            metadata:
              schema: metadata/Document/v1
              name: application-api
              storagePolicy: cleartext
            data: |-
              -----BEGIN CERTIFICATE-----
              MIIDYDCCAkigAwIBAgIUKG41PW4VtiphzASAMY4/3hL8OtAwDQYJKoZIhvcNAQEL
              ...snip...
              P3WT9CfFARnsw2nKjnglQcwKkKLYip0WY2wh3FE7nrQZP6xKNaSRlh6p2pCGwwwH
              HkvVwA==
              -----END CERTIFICATE-----
            ...
        """

    def gen(self):
        raise NotImplementedError()

    def gen_test(self, schema, storage_policy, data=None):
        if data is None:
            data = test_utils.rand_password()

        document_secret_template = copy.deepcopy(self.DOCUMENT_SECRET_TEMPLATE)

        document_secret_template['metadata']['storagePolicy'] = storage_policy
        document_secret_template['schema'] = (
            document_secret_template['schema'] % schema)
        document_secret_template['data'] = data

        return document_secret_template


class ValidationPolicyFactory(DeckhandFactory):
    """Class for auto-generating validation policy templates for testing."""

    VALIDATION_POLICY_TEMPLATE = {
        "data": {
            "validations": []
        },
        "metadata": {
            "schema": "metadata/Control/%s" % DeckhandFactory.API_VERSION,
            "name": ""
        },
        "schema": types.VALIDATION_POLICY_SCHEMA
    }

    def __init__(self):
        """Constructor for ``ValidationPolicyFactory``.

        Returns a template whose YAML representation is of the form::

            ---
            schema: deckhand/ValidationPolicy/v1.0
            metadata:
              schema: metadata/Control/v1.0
              name: site-deploy-ready
            data:
              validations:
                - name: deckhand-schema-validation
                - name: drydock-site-validation
                  expiresAfter: P1W
                - name: promenade-site-validation
                  expiresAfter: P1W
                - name: armada-deployability-validation
            ...
        """

    def gen(self, validation_type, status):
        if validation_type not in types.DECKHAND_VALIDATION_TYPES:
            raise ValueError("The validation type must be in %s."
                             % types.DECKHAND_VALIDATION_TYPES)

        validation_policy_template = copy.deepcopy(
            self.VALIDATION_POLICY_TEMPLATE)

        validation_policy_template['metadata'][
            'name'] = test_utils.rand_name('validation-policy')
        validation_policy_template['data']['validations'] = [
            {'name': validation_type, 'status': status}
        ]

        return validation_policy_template

    def gen_test(self, name=None, num_validations=None):
        """Generate the test document template.

        Generate the document template based on the arguments passed to
        the constructor and to this function.
        """
        if not(num_validations and isinstance(num_validations, int)
               and num_validations > 0):
            raise ValueError('The "num_validations" attribute must be integer '
                             'value > 1.')

        if not name:
            name = test_utils.rand_name('validation-policy')
        if not num_validations:
            num_validations = 3

        validations = [
            test_utils.rand_name('validation-name')
            for _ in range(num_validations)]

        validation_policy_template = copy.deepcopy(
            self.VALIDATION_POLICY_TEMPLATE)
        validation_policy_template['metadata']['name'] = name
        validation_policy_template['data']['validations'] = validations

        return validation_policy_template
