..
  Copyright 2018 AT&T Intellectual Property.
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

.. _replacement:

Document Replacement
====================

.. note::

  Document replacement is an advanced concept in Deckhand. This section assumes
  that the reader already has an understanding of :ref:`layering` and
  :ref:`substitution`.

Document replacement, in the simplest terms, involves a *child* document
replacing its *parent*. That is, the *entire* child document replaces its
parent document. Replacement aims to lessen data duplication by taking
advantage of :ref:`document-abstraction` and document layering patterns.

Unlike the :ref:`layering` ``replace`` action, which allows a child document
to selectively replace portions of the parent's ``data`` section with that of
its own, document replacement allows a child document to replace the *entire*
parent document.

.. todo::

  Elaborate on these patterns in a separate section.

Replacement introduces the ``replacement: true`` property underneath the
top-level ``metadata`` section. This property is subject to certain
preconditions, discussed in the `Requirements`_ section below.

Replacement aims to replace specific values in a parent document via
document replacement for particular sites, while allowing the same parent
document to be consumed directly (layered with, substituted from) for
completely different sites. This means that the same YAML template can be
referenced from a global namespace by different site-level documents, and when
necessary, specific sites can override the global defaults with specific
overrides via document replacement. Effectively, this means that the same
template can be referenced without having to duplicate all of its data, just to
override a few values between the otherwise-exactly-the-same templates.

Like abstract documents, documents that **are replaced** are not returned
from Deckhand's ``rendered-documents`` endpoint. (Documents that
**do replace** -- those with the ``replacement: true`` property -- are
returned instead.)

Requirements
------------

Document replacement has the following requirements:

* Only a child document can replace its parent.
* The child document must have the ``replacement: true`` property underneath
  its ``metadata`` section.
* The child document must be able to select the correct parent. For more
  information on this, please reference the :ref:`parent-selection` section.
* Additionally, the child document must have the **same** ``metadata.name``
  and ``schema`` as its parent. Their ``metadata.layeringDefinition.layer``
  must **differ**.

The following result in validation errors:

* A document with ``replacement: true`` doesn't have a parent.
* A document with ``replacement: true`` doesn't have the same
  ``metadata.name`` and ``schema`` as its parent.
* A replacement document cannot itself be replaced. That is, only one level
  of replacement is allowed.

Note that each key in the examples below is *mandatory* and that the
``parentSelector`` labels should be able to select the parent to be replaced.

Document **replacer** (child):

::

  ---
  # Note that the schema and metadata.name keys are the same as below.
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand
    # The replacement: true key is mandatory.
    replacement: true
    layeringDefinition:
      # Note that the layer differs from that of the parent below.
      layer: N-1
      # The key-value pairs underneath `parentSelector` must be compatible with
      # key-value pairs underneath the `labels` section in the parent document
      # below.
      parentSelector:
        selector: foo
      actions:
        - ...
  data: ...

Which replaces the document **replacee** (parent):

::

  ---
  # Note that the schema and metadata.name keys are the same as above.
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand
    labels:
      selector: foo
    layeringDefinition:
      # Note that the layer differs from that of the child above.
      layer: N
  data: ...

Why Replacement?
----------------

Layering without Replacement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Layering without replacement can introduce a lot of data duplication across
documents. Take the following use case: Some sites need to be deployed with
log debugging *enabled* and other sites need to be deployed with log debugging
*disabled*.

To achieve this, two top-layer documents can be created:

::

  ---
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand-1
    layeringDefinition:
      layer: global
      ...
  data:
    debug: false
    # Note that the data below can be arbitrarily long and complex.
    ...

And:

::

  ---
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand-2
    layeringDefinition:
      layer: global
      ...
  data:
    debug: true
    # Note that the data below can be arbitrarily long and complex.
    ...

However, what if the only thing that differs between the two documents is just
``debug: true|false`` and every other value in both documents is precisely the
same?

Clearly, the pattern above leads to a lot of data duplication.

Layering with Replacement
^^^^^^^^^^^^^^^^^^^^^^^^^

Using document replacement, the above duplication can be partially eliminated.
For example:

::

  # Replacer (child document).
  ---
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand
    replacement: true
    layeringDefinition:
      layer: site
      parentSelector:
        selector: foo
      actions:
        - method: merge
          path: .
        - method: replace
          path: .debug
  data:
    debug: true
    ...

And:

::

  # Replacee (parent document).
  ---
  schema: armada/Chart/v1
  metadata:
    name: airship-deckhand
    labels:
      selector: foo
    layeringDefinition:
      layer: global
      ...
  data:
    debug: false
    ...

In the case above, for sites that require ``debug: false``, only the
global-level document should be included in the payload to Deckhand, along
with all other documents required for site deployment.

However, for sites that require ``debug: true``, both documents should be
included in the payload to Deckhand, along with all other documents required
for site deployment.

Implications for Pegleg
^^^^^^^^^^^^^^^^^^^^^^^

In practice, when using `Pegleg`_, each document above can be placed in a
separate file and Pegleg can either reference *only* the parent document
if log debugging needs to be enabled or *both* documents if log debugging
needs to be disabled. This pattern allows data duplication to be lessened.

.. _Pegleg: http://pegleg.readthedocs.io/en/latest/

How It Works
------------

Document replacement involves a child document replacing its parent. There
are three fundamental cases that are handled:

#. A child document replaces its parent. Only the child is returned.
#. Same as (1), except that the parent document is used as a substitution
   source. With replacement, the child is used as the substitution source
   instead.
#. Same as (2), except that the parent document is used as a layering
   source (that is, yet another child document layers with the parent). With
   replacement, the child is used as the layering source instead.
