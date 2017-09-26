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

=======
Testing
=======

Unit testing
============

Unit testing currently uses an in-memory sqlite database. Since Deckhand's
primary function is to serve as the back-end storage for UCP, the majority
of unit tests perform actual database operations. Mocking is used sparingly
because Deckhand is a fairly insular application that lives at the bottom
of a very deep stack; Deckhand only communicates with Keystone and Barbican.
As such, validating database operations is paramount to correctly testing
Deckhand.

To run unit tests using sqlite, execute::

    $ tox -epy27
    $ tox -epy35

against a py27- or py35-backed environment, respectively. To run individual
unit tests, run::

    $ tox -e py27 -- deckhand.tests.unit.db.test_revisions

for example.

To run unit tests using postgresql, execute::

    $ tox -epy27-postgresql
    $ tox -epy35-postgresql

against a py27- or py35-backed environment, respectively. Individual unit tests
can be executed the same way as above.

`pifpaf <https://github.com/jd/pifpaf>`_ is used to spin up a temporary
postgresql database. The URL is set up as an environment variable via
``PIFPAF_URL``.

.. warning::

    It is **not** recommended to run postgresql-backed unit tests concurrently.
    Only run them serially. This is because, to guarantee true test isolation,
    the DB tables are re-created each test run. Only one instance of postgresql
    is created across all threads, thus causing major conflicts if concurrency
    > 1.

Functional testing
==================

Prerequisites
-------------
Deckhand requires Docker to run its functional tests. A basic installation
guide for Docker for Ubuntu can be found
`here <https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/>`_.

Overview
--------
Deckhand uses `gabbi <https://github.com/cdent/gabbi>`_ as its functional
testing framework. Functional tests can be executed via::

    $ tox -e functional

You can also run a subset of tests via a regex::

    $ tox -e functional -- gabbi.suitemaker.test_gabbi_document-crud-success-multi-bucket

The command executes ``tools/functional-tests.sh`` which:

    1) Launches Postgresql inside a Docker container.
    2) Sets up a basic Deckhand configuration file that uses Postgresql
       in its ``oslo_db`` connection string.
    3) Sets up a custom policy file with very liberal permissions so that
       gabbi can talk to Deckhand without having to authenticate against
       Keystone and pass an admin token to Deckhand.
    4) Instantiates Deckhand via ``uwisgi``.
    5) Calls gabbi which runs a battery of functional tests.

At this time, there are no functional tests for policy enforcement
verification. Negative tests will be added at a later date to confirm that
a 403 Forbidden is raised for each endpoint that does policy enforcement
absent necessary permissions.
