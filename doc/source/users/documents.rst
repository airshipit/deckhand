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

Documents
=========

All configuration data is stored entirely as structured documents, for which
schemas must be registered. Documents satisfy the following use cases:

  * layering - helps reduce duplication in configuration while maintaining
    auditability across many sites
  * substitution - provides separation between secret data and other
    configuration data, while allowing a simple interface for clients
  * revision history - improves auditability and enables services to provide
    functional validation of a well-defined collection of documents that are
    meant to operate together
  * validation - allows services to implement and register different kinds of
    validations and report errors

Detailed documentation for :ref:`layering`, :ref:`substitution`,
:ref:`revision-history` and :ref:`validation` should be reviewed for a more
thorough understanding of each concept.

.. _document-format:

Document Format
---------------

The document format is modeled loosely after Kubernetes practices. The top
level of each document is a dictionary with 3 keys: ``schema``, ``metadata``,
and ``data``.

* ``schema`` - Defines the name of the JSON schema to be used for validation.
  Must have the form: ``<namespace>/<kind>/<version>``, where the meaning of
  each component is:

  * ``namespace`` - Identifies the owner of this type of document. The values
    ``deckhand`` and ``metadata`` are reserved for internal use.
  * ``kind`` - Identifies a type of configuration resource in the namespace.
  * ``version`` - Describe the version of this resource, e.g. ``v1``.

* ``metadata`` - Defines details that Deckhand will inspect and understand.
  There are multiple schemas for this section as discussed below. All the
  various types of metadata include a ``metadata.name`` field which must be
  unique for each document ``schema``.
* ``data`` - Data to be validated by the schema described by the ``schema``
  field. Deckhand only interacts with content here as instructed to do so by
  the ``metadata`` section. The form of this section is considered to be
  completely owned by the ``namespace`` in the ``schema``.

At the **database** level, documents are uniquely identified by the combination
of:

#. ``metadata.name``
#. ``schema``
#. ``metadata.layeringDefinition.layer``

This means that raw revision documents -- which are persisted in Deckhand's
database -- require that the combination of all 3 parameters be unique.

However, **post-rendered documents** are only uniquely identified by the
combination of:

#. ``metadata.name``
#. ``schema``

Because collisions with respect to the third parameter --
``metadata.layeringDefinition.layer`` -- can only occur with
:ref:`replacement`. But after document rendering, the replacement-parent
documents are never returned.

Below is a fictitious example of a complete document, which illustrates all the
valid fields in the ``metadata`` section:

.. code-block:: yaml

      ---
      schema: some-service/ResourceType/v1
      metadata:
        schema: metadata/Document/v1
        name: unique-name-given-schema
        storagePolicy: cleartext
        labels:
          genesis: enabled
          master: enabled
        layeringDefinition:
          abstract: true
          layer: region
          parentSelector:
            required_key_a: required_label_a
            required_key_b: required_label_b
          actions:
            - method: merge
              path: .path.to.merge.into.parent
            - method: delete
              path: .path.to.delete
        substitutions:
          - dest:
              path: .substitution.target
            src:
              schema: another-service/SourceType/v1
              name: name-of-source-document
              path: .source.path
      data:
        path:
          to:
            merge:
              into:
                parent:
                  foo: bar
                ignored:
                  data: here
        substitution:
          target: null

Document Metadata
^^^^^^^^^^^^^^^^^

There are 2 supported kinds of document metadata. Documents with ``Document``
metadata are the most common, and are used for normal configuration data.
Documents with ``Control`` metadata are used to customize the behavior of
Deckhand.

schema: metadata/Document/v1
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This type of metadata allows the following metadata hierarchy:

* ``name`` - string, required - Unique within a revision for a given ``schema``
  and ``metadata.layeringDefinition.layer``.
* ``storagePolicy`` - string, required - Either ``cleartext`` or ``encrypted``.
  If ``encyrpted`` is specified, then the ``data`` section of the document will
  be stored in a secure backend (likely via OpenStack Barbican). ``metadata``
  and ``schema`` fields are always stored in cleartext. More information
  on document encryption is available :ref:`here <encryption>`.
* ``layeringDefinition`` - dict, required - Specifies layering details. See the
  Layering section below for details.

  * ``abstract`` - boolean, required - An abstract document is not expected to
    pass schema validation after layering and substitution are applied.
    Non-abstract (concrete) documents are.
  * ``layer`` - string, required - References a layer in the ``LayeringPolicy``
    control document.
  * ``parentSelector`` - labels, optional - Used to construct document chains for
    executing merges.
  * ``actions`` - list, optional - A sequence of actions to apply this documents
    data during the merge process.
    * ``method`` - string, required - How to layer this content.
    * ``path`` - string, required - What content in this document to layer onto
    parent content.

* ``substitutions`` - list, optional - A sequence of substitutions to apply. See
  the Substitutions section for additional details.

  * ``dest`` - dict, required - A description of the inserted content destination.

    * ``path`` - string, required - The JSON path where the data will be placed
      into the ``data`` section of this document.
    * ``pattern`` - string, optional - A regex to search for in the string
      specified at ``path`` in this document and replace with the source data

  * ``src`` - dict, required - A description of the inserted content source.

    * ``schema`` - string, required - The ``schema`` of the source document.
    * ``name`` - string, required - The ``metadata.name`` of the source document.
    * ``path`` - string, required - The JSON path from which to extract data in
      the source document relative to its ``data`` section.


schema: metadata/Control/v1
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This schema is the same as the ``Document`` schema, except it omits the
``storagePolicy``, ``layeringDefinition``, and ``substitutions`` keys, as these
actions are not supported on ``Control`` documents.

The complete list of valid ``Control`` document kinds is specified below along
with descriptions of each document kind.

.. _document-abstraction:

Document Abstraction
--------------------

Document abstraction can be compared to an abstract class in programming
languages: The idea is to declare an abstract base class used for declaring
common data to be overridden and customized by subclasses. In fact,
this is the predominant use case for document abstraction: Defining base
abstract documents that other concrete (non-abstract) documents can
layer with.

An abstract document is a document whose ``metadata.abstract`` property is
True. A concrete document is a document whose ``metadata.abstract`` property
is False. Concrete and non-abstract are terms that are used interchangeably.

In Deckhand, document abstraction has certain implications:

* An abstract document, like all other documents, will be persisted in
  Deckhand's database and will be subjected to :ref:`revision-history`.
* However, abstract documents are **not** returned by Deckhand's
  ``rendered-documents`` endpoint: That is, rendered documents never include
  abstract documents.
* Concrete documents **can** layer with abstract documents -- and this is
  encouraged.
* Abstract documents **can** layer with other documents as well -- but unless
  a concrete document layers with or substitutes from the resultant abstract
  document, no meaningful data will be returned via rendering, as only
  concrete documents are returned.
* Likewise, abstract documents **can** substitute from other documents. The
  same reasoning as the bullet point above applies.
* However, abstract documents **cannot** be used as substitution sources.
  Only concrete documents may be used as substitution sources.
