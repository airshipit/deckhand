..
  Copyright 2017 AT&T Intellectual Property.
  All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License"); you may
  not use this file except in compliance with the License. You may obtain
  a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
  License for the specific language governing permissions and limitations
  under the License.

.. _layering:

Document Layering
=================

Layering provides a restricted data inheritance model intended to help reduce
duplication in configuration. Documents with different ``schema``'s are never
layered together (see the :ref:`substitution` section if you need to combine data
from multiple types of documents).

Layering is controlled in two places:

1. The ``LayeringPolicy`` control document (described below), which defines the
   valid layers and their order of precedence.
2. In the ``metadata.layeringDefinition`` section of normal
   (``metadata.schema=metadata/Document/v1``) documents.

When rendering a particular document, you resolve the chain of parents upward
through the layers, and begin working back down each layer rendering at each
document in the chain.

When rendering each layer, the parent document is used as the starting point,
so the entire contents of the parent are brought forward.  Then the list of
`actions` will be applied in order.  Supported actions are:

* ``merge`` - "deep" merge child data at the specified path into the existing data
* ``replace`` - overwrite existing data with child data at the specified path
* ``delete`` - remove the existing data at the specified path

After actions are applied for a given layer, substitutions are applied (see
the Substitution section for details).

Selection of document parents is controlled by the ``parentSelector`` field and
works as follows. A given document, ``C``, that specifies a ``parentSelector``
will have exactly one parent, ``P``. Document ``P`` will be the highest
precedence (i.e. part of the lowest layer defined in the ``layerOrder`` list
from the ``LayeringPolicy``) document that has the labels indicated by the
``parentSelector`` (and possibly additional labels) from the set of all
documents of the same ``schema`` as ``C`` that are in layers above the layer ``C``
is in. For example, consider the following sample documents:

.. code-block:: yaml

  ---
  schema: deckhand/LayeringPolicy/v1
  metadata:
    schema: metadata/Control/v1
    name: layering-policy
  data:
    layerOrder:
      - global
      - region
      - site
  ---
  schema: example/Kind/v1
  metadata:
    schema: metadata/Document/v1
    name: global-1234
    labels:
      key1: value1
    layeringDefinition:
      abstract: true
      layer: global
  data:
    a:
      x: 1
      y: 2
  ---
  schema: example/Kind/v1
  metadata:
    schema: metadata/Document/v1
    name: region-1234
    labels:
      key1: value1
    layeringDefinition:
      abstract: true
      layer: region
      parentSelector:
        key1: value1
      actions:
        - method: replace
          path: .a
  data:
    a:
      z: 3
  ---
  schema: example/Kind/v1
  metadata:
    schema: metadata/Document/v1
    name: site-1234
    layeringDefinition:
      layer: site
      parentSelector:
        key1: value1
      actions:
        - method: merge
          path: .
  data:
    b: 4

When rendering, the parent chosen for ``site-1234`` will be ``region-1234``,
since it is the highest precedence document that matches the label selector
defined by ``parentSelector``, and the parent chosen for ``region-1234`` will be
``global-1234`` for the same reason. The rendered result for ``site-1234`` would
be:

.. code-block:: yaml

  ---
  schema: example/Kind/v1
  metadata:
    name: site-1234
  data:
    a:
      z: 3
    b: 4

If ``region-1234`` were later removed, then the parent chosen for `site-1234`
would become ``global-1234``, and the rendered result would become:

.. code-block:: yaml

  ---
  schema: example/Kind/v1
  metadata:
    name: site-1234
  data:
    a:
      x: 1
      y: 2
    b: 4

.. TODO: Add figures for this example, with region present, have site point
.. with dotted line at global and indicate in caption (or something) that it's
.. selected for but ignored, because there's a higher-precedence layer to select
