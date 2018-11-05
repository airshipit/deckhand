..
  Copyright 2018 AT&T Intellectual Property.  All other rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.


Deckhand Configuration
======================

Cache Configuration
-------------------

Deckhand currently uses 3 different caches for the following use cases:

* Caching rendered documents (see :ref:`rendering`) for faster future look-ups
* Caching Barbican secret payloads
* Caching ``jsonschema`` results for quickly resolving deeply nested dictionary
  data

All 3 caches are implemented in memory.

Please reference the configuration groups below to enable or customize the
timeout for each cache:

* ``[barbican]``
* ``[engine]``
* ``[jsonschema]``

Sample Configuration File
-------------------------

The following is a sample Deckhand config file for adaptation and use. It is
auto-generated from Deckhand when this documentation is built, so
if you are having issues with an option, please compare your version of
Deckhand with the version of this documentation.

The sample configuration can also be viewed in `file form <_static/deckhand.conf.sample>`_.

.. literalinclude:: ../_static/deckhand.conf.sample
