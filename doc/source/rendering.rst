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
Deckhand's database, retrieving encrypted information from Barbican,
and applying substitution, layering and replacement algorithms on the
data.

The following algorithms are involved during the rendering process:

:ref:`substitution`
-------------------

Substitution provides an "open" data sharing model in which any source
document can be used to substitute data into any destination document.

:ref:`layering`
---------------

Layering provides a "restricted" data inheritance model intended to help
reduce duplication in configuration.

:ref:`replacement`
------------------

Replacement builds on top of layering to provide yet another mechanism
for reducing data duplication.
