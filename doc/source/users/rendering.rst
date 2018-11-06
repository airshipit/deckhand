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

.. _rendering:

Document Rendering
==================

Document rendering involves extracting all raw revision documents from
Deckhand's database, retrieving encrypted information from `Barbican`_,
and applying substitution, layering and replacement algorithms on the
data.

The following algorithms are involved during the rendering process:

:ref:`substitution`
-------------------

Substitution provides an "open" data sharing model in which any source
document can be used to substitute data into any destination document.

Use Cases
^^^^^^^^^

* Sharing of data between specific documents no matter their ``schema``.
* Data sharing using pattern matching.
* Fine-grained sharing of specific sections of data.

:ref:`layering`
---------------

Layering provides a "restricted" data inheritance model intended to help
reduce duplication in configuration.

Use Cases
^^^^^^^^^

* Sharing of data between documents with the same ``schema``.
* Deep merging of objects and lists.
* Layer order with multiple layers, resulting in a larger hierarchy of
  documents.
* Source document for data sharing can be identified via labels, allowing for
  different documents to be used as the source for sharing, depending on
  :ref:`parent-selection`.

:ref:`replacement`
------------------

Replacement builds on top of layering to provide yet another mechanism
for reducing data duplication.

Use Cases
^^^^^^^^^

* Same as layering, but with a need to replace higher-layer documents with
  lower-layer documents for specific site deployments.

.. _Barbican: https://docs.openstack.org/barbican/latest/api/
