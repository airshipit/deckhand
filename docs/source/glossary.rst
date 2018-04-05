..
   Copyright 2017 AT&T Intellectual Property.  All other rights reserved.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

========
Glossary
========

A
~

.. glossary::

   Alembic

       Database migration software for Python and SQLAlchemy based databases.

B
~

.. glossary::

   barbican

      Code name of the :term:`Key Manager service
      <Key Manager service (barbican)>`.

   bucket

      A bucket manages collections of documents together, providing write
      protections around them.

D
~

.. glossary::

   document

      A collection of metadata and data in YAML format. The data document
      format is modeled loosely after Kubernetes practices. The top level of
      each document is a dictionary with 3 keys: `schema`, `metadata`, and
      `data`.

K
~

.. glossary::

   Key Manager service (barbican)

      The project that produces a secret storage and
      generation system capable of providing key management for
      services wishing to enable encryption features.

M
~

.. glossary::

   migration (databse)

       A transformation of a databse from one version or structure to another.
       Migrations for Deckhand's database are performed using Alembic.

S
~

.. glossary::

   SQLAlchemy

      Databse toolkit for Python.

U
~

.. glossary::

   UCP

      Acronym for the Undercloud Platform.
