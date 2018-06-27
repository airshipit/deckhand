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

Introduction
------------

Layering provides a restricted data inheritance model intended to help reduce
duplication in configuration. With layering, child documents can inherit
data from parent documents. Through :ref:`layering-actions`, child documents
can control exactly what they inherit from their parent. Document layering,
conceptually speaking, works much like class inheritance: A child class
inherits all variables and methods from its parent, but can elect to override
its parent's functionality.

Goals behind layering include:

* model site deployment data hierarchically
* lessen data duplication across site layers (as well as other conceptual
  layers)

Document Abstraction
^^^^^^^^^^^^^^^^^^^^

Layering works with :ref:`document-abstraction`: child documents can inherit
from abstract as well as concrete parent documents.

Pre-Conditions
^^^^^^^^^^^^^^

A document only has one parent, but its parent is computed dynamically using
the :ref:`parent-selection` algorithm. That is, the notion of
"multiple inheritance" **does not** apply to document layering.

Documents with different ``schema`` values are never layered together (see the
:ref:`substitution` section if you need to combine data from multiple types of
documents).

Document layering requires a :ref:`layering-policy` to exist in the revision
whose documents will be layered together (rendered). An error will be issued
otherwise.

Terminology
-----------

.. note::

  Whether a layer is "lower" or "higher" has entirely to do with its order of
  initialization in a ``layerOrder`` and, by extension, its precedence in the
  :ref:`parent-selection` algorithm described below.

* Layer - A position in a hierarchy used to control :ref:`parent-selection` by
  the :ref:`layering-algorithm`. It can be likened to a position in an
  inheritance hierarchy, where ``object`` in Python can be likened to the
  highest layer in a ``layerOrder`` in Deckhand and a leaf class can be likened
  to the lowest layer in a ``layerOrder``.
* Child - Meaningful only in a parent-child document relationship. A document
  with a lower layer (but higher priority) than its parent, determined using
  using :ref:`parent-selection`.
* Parent - Meaningful only in a parent-child document relationship. A document
  with a higher layer (but lower priority) than its child.
* Layering Policy - A :ref:`control document <control-documents>` that defines
  the strict ``layerOrder`` in which documents are layered together. See
  :ref:`layering-policy` documentation for more information.
* Layer Order (``layerOrder``) - Corresponds to the ``data.layerOrder`` of the
  :ref:`layering-policy` document. Establishes the layering hierarchy for a
  set of layers in the system.
* Layering Definition (``layeringDefinition``) - Metadata in each document for
  controlling the following:

  * ``layer``: the document layer itself
  * ``parentSelector``: :ref:`parent-selection`
  * ``abstract``: :ref:`document-abstraction`
  * ``actions``: :ref:`layering-actions`

* Parent Selector (``parentSelector``) - Key-value pairs or labels for
  identifying the document's parent. Note that these key-value pairs are not
  unique and that multiple documents can use them. All the key-value pairs
  in the ``parentSelector`` must be found among the target parent's
  ``metadata.labels``: this means that the ``parentSelector`` key-value pairs
  must be a subset of the target parent's ``metadata.labels`` key-value
  pairs. See :ref:`parent-selection` for further details.
* Layering Actions (``actions``) - A list of actions that control what data
  are inherited from the parent by the child. See :ref:`layering-actions`
  for further details.

.. _layering-algorithm:

Algorithm
---------

Layering is applied at the bottommost layer of the ``layerOrder`` first and
at the topmost layer of the ``layerOrder`` last, such that the "base" layers
are processed first and the "leaf" layers are processed last. For each
layer in the ``layerOrder``, the documents that correspond to that layer
are retrieved. For each document retrieved, the ``layerOrder`` hierarchy
is resolved using :ref:`parent-selection` to identify the parent document.
Finally, the current document is layered with its parent using
:ref:`layering-actions`.

After layering is complete, the :ref:`substitution` algorithm is applied to the
*current* document, if applicable.

.. _layering-configuration:

Layering Configuration
----------------------

Layering is configured in 2 places:

#. The ``LayeringPolicy`` control document (described in
   :ref:`layering-policy`), which defines the valid layers and their order of
   precedence.
#. In the ``metadata.layeringDefinition`` section of normal
   (``metadata.schema=metadata/Document/v1``) documents. For more information
   about document structure, reference :ref:`document-format`.

An example ``layeringDefinition`` may look like::

  layeringDefinition:
    # Controls whether the document is abstract or concrete.
    abstract: true
    # A layer in the ``layerOrder``. Must be valid or else an error is raised.
    layer: region
    # Key-value pairs or labels for identifying the document's parent.
    parentSelector:
      required_key_a: required_label_a
      required_key_b: required_label_b
    # Actions which specify which data to add to the child document.
    actions:
      - method: merge
        path: .path.to.merge.into.parent
      - method: delete
        path: .path.to.delete

.. _layering-actions:

Layering Actions
----------------

Introduction
^^^^^^^^^^^^

Layering actions allow child documents to modify data that is inherited from
the parent. What if the child document should only inherit some of the parent
data? No problem. A merge action can be performed, followed by ``delete``
and ``replace`` actions to trim down on what should be inherited.

Each layer action consists of an ``action`` and a ``path``. Whenever *any*
action is specified, *all* the parent data is automatically inherited by the
child document. The ``path`` specifies which data from the *child* document to
**prioritize over** that of the parent document. Stated differently, all data
from the parent is considered while *only* the *child* data at ``path`` is
considered during an action. However, whenever a conflict occurs during an
action, the *child* data takes priority over that of the parent.

Layering actions are queued -- meaning that if a ``merge`` is
specified before a ``replace`` then the ``merge`` will *necessarily* be
applied before the ``replace``. For example, a ``merge`` followed by a
``replace`` **is not necessarily** the same as a ``replace`` followed by a
``merge``.

Layering actions can be applied to primitives, lists and dictionaries alike.

Action Types
^^^^^^^^^^^^

Supported actions are:

* ``merge`` - "deep" merge child data and parent data into the child ``data``,
  at the specified `JSONPath`_

  .. note::

    For conflicts between the child and parent data, the child document's
    data is **always** prioritized. No other conflict resolution strategy for
    this action currently exists.

  ``merge`` behavior depends upon the data types getting merged. For objects
  and lists, Deckhand uses `JSONPath`_ resolution to retrieve data from those
  entities, after which Deckhand applies merge strategies (see below) to
  combine merge child and parent data into the child document's ``data``
  section.

  **Merge Strategies**

  Deckhand applies the following merge strategies for each data type:

  * object: "Deep-merge" child and parent data together; conflicts are resolved
    by prioritizing child data over parent data. "Deep-merge" means
    recursively combining data for each key-value pair in both objects.
  * array: The merge strategy involves:

    * When using an index in the action ``path`` (e.g. ``a[0]``):

      #. Copying the parent array into the child's ``data`` section at the
         specified JSONPath.
      #. Appending each child entry in the original child array into the parent
         array. This behavior is synonymous with the ``extend`` list function
         in Python.

    * When not using an index in the action ``path`` (e.g. ``a``):

      #. The child's array replaces the parent's array.
  * primitives: Includes all other data types, except for ``null``. In this
    case JSONPath resolution is impossible, so child data is prioritized over
    that of the parent.

  **Examples**

  Given::

    Child Data:    ``{'a': {'x': 7, 'z': 3}, 'b': 4}``
    Parent Data:   ``{'a': {'x': 1, 'y': 2}, 'c': 9}``

  * When::

      Merge Path: ``.``

    Then::

      Rendered Data: ``{'a': {'x': 7, 'y': 2, 'z': 3}, 'b': 4, 'c': 9}``

      All data from parent is automatically considered, all data from child
      is considered due to ``.`` (selects everything), then both merged.

  * When::

      Merge Path: ``.a``

    Then::

      Rendered Data: ``{'a': {'x': 7, 'y': 2, 'z': 3}, 'c': 9}``

      All data from parent is automatically considered, all data from child
      at ``.a`` is considered, then both merged.

  * When::

      Merge Path: ``.b``

    Then::

      Rendered Data: ``{'a': {'x': 1, 'y': 2}, 'b': 4, 'c': 9}``

      All data from parent is automatically considered, all data from child
      at ``.b`` is considered, then both merged.

  * When::

      Merge Path: ``.c``

    Then::

      Error raised (``.c`` missing in child).

* ``replace`` - overwrite existing data with child data at the specified
  JSONPath.

  **Examples**

  Given::

    Child Data:    ``{'a': {'x': 7, 'z': 3}, 'b': 4}``
    Parent Data:   ``{'a': {'x': 1, 'y': 2}, 'c': 9}``

  * When::

      Replace Path: ``.``

    Then::

      Rendered Data: ``{'a': {'x': 7, 'z': 3}, 'b': 4}``

      All data from parent is automatically considered, but is replaced by all
      data from child at ``.`` (selects everything), so replaces everything
      in parent.

  * When::

      Replace Path: ``.a``

    Then::

      Rendered Data: ``{'a': {'x': 7, 'z': 3}, 'c': 9}``

      All data from parent is automatically considered, but is replaced by all
      data from child at ``.a``, so replaces all parent data at ``.a``.

  * When::

      Replace Path: ``.b``

    Then::

      Rendered Data: ``{'a': {'x': 1, 'y': 2}, 'b': 4, 'c': 9}``

      All data from parent is automatically considered, but is replaced by all
      data from child at ``.b``, so replaces all parent data at ``.b``.

      While ``.b`` isn't in the parent, it only needs to exist in the child.
      In this case, something (from the child) replaces nothing (from the
      parent).

  * When::

      Replace Path: ``.c``

    Then::

      Error raised (``.c`` missing in child).

* ``delete`` - remove the existing data at the specified JSONPath.

  **Examples**

  Given::

    Child Data:    ``{'a': {'x': 7, 'z': 3}, 'b': 4}``
    Parent Data:   ``{'a': {'x': 1, 'y': 2}, 'c': 9}``

  * When::

      Delete Path: ``.``

    Then::

      Rendered Data: ``{}``

      Note that deletion of everything results in an empty dictionary by
      default.

  * When::

      Delete Path: ``.a``

    Then::

      Rendered Data: ``{'c': 9}``

      All data from Parent Data at ``.a`` was deleted, rest copied over.

  * When::

      Delete Path: ``.c``

    Then::

      Rendered Data: ``{'a': {'x': 1, 'y': 2}}``

      All data from Parent Data at ``.c`` was deleted, rest copied over.

  * When::

      Replace Path: ``.b``

    Then::

      Error raised (``.b`` missing in child).

After actions are applied for a given layer, substitutions are applied (see
the :ref:`substitution` section for details).

.. _JSONPath: http://goessner.net/articles/JsonPath/

.. _parent-selection:

Parent Selection
----------------

Parent selection is performed dynamically. Unlike :ref:`substitution`,
parent selection does not target a specific document using ``schema`` and
``name`` identifiers. Rather, parent selection respects the ``layerOrder``,
selecting the highest precedence parent in accordance with the algorithm that
follows. This allows flexibility in parent selection: if a document's immediate
parent is removed in a revision, then, if applicable, the grandparent (in the
previous revision) can become the document's parent (in the latest revision).

Selection of document parents is controlled by the ``parentSelector`` field and
works as follows:

* A given document, ``C``, that specifies a ``parentSelector``, will have
  exactly one parent, ``P``. If comparing layering with inheritance,
  layering, then, does *not* allow multi-inheritance.
* Both ``C`` and ``P`` must have the **same** ``schema``.
* Both ``C`` and ``P`` should have **different** ``metadata.name`` values
  except in the case of :ref:`replacement`.
* Document ``P`` will be the highest-precedence document whose
  ``metadata.labels`` are a **superset** of document C's ``parentSelector``.
  Where:

  * Highest precedence means that ``P`` belongs to the lowest layer
    defined in the ``layerOrder`` list from the ``LayeringPolicy`` which is
    at least one level higher than the layer for ``C``. For example, if ``C``
    has layer ``site``, then its parent ``P`` must at least have layer ``type``
    or above in the following ``layerOrder``:

    ::

      ---
      ...
      layerOrder:
        - global # Highest layer
        - type
        - site   # Lowest layer

  * Superset means that ``P`` **at least** has all the labels in its
    ``metadata.labels`` that child ``C`` references via its ``parentSelector``.
    In other words, parent ``P`` can have more labels than ``C`` uses
    to reference it, but ``C`` must at least have one matching label in its
    ``parentSelector`` with ``P``.

* Deckhand will select ``P`` if it belongs to the highest-precedence layer.
  For example, if ``C`` belongs to layer ``site``, ``P`` belongs to layer
  ``type``, and ``G`` belongs to layer ``global``, then Deckhand will use
  ``P`` as the parent for ``C``. If ``P`` is non-existent, then ``G``
  will be selected instead.

For example, consider the following sample documents:

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
