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

.. _testing:

=======
Testing
=======

.. note::

  Deckhand has only been tested against a Ubuntu 16.04 environment. The guide
  below assumes the user is using Ubuntu.

Unit testing
============

Prerequisites
-------------

`pifpaf <https://github.com/jd/pifpaf>`_ is used to spin up a temporary
postgresql database for unit tests. The DB URL is set up as an environment
variable via ``PIFPAF_URL`` which is referenced by Deckhand's unit test suite.

#. PostgreSQL must be installed. To do so, run::

     $ sudo apt-get update
     $ sudo apt-get install postgresql postgresql-contrib -y

#. When running ``pifpaf run postgresql`` (implicitly called by unit tests below),
   pifpaf uses ``pg_config`` which can be installed by running::

     $ sudo apt-get install libpq-dev -y

Overview
--------

Unit testing currently uses an in-memory SQLite database. Since Deckhand's
primary function is to serve as the back-end storage for Airship, the majority
of unit tests perform actual database operations. Mocking is used sparingly
because Deckhand is a fairly insular application that lives at the bottom
of a very deep stack; Deckhand only communicates with Keystone and Barbican.
As such, validating database operations is paramount to correctly testing
Deckhand.

To run unit tests using SQLite, execute::

    $ tox -epy35

against a py35-backed environment, respectively.

To run unit tests using PostgreSQL, execute::

    $ tox -epy35-postgresql

To run individual unit tests, run (for example)::

    $ tox -e py35 -- deckhand.tests.unit.db.test_revisions

.. warning::

    It is **not** recommended to run postgresql-backed unit tests concurrently.
    Only run them serially. This is because, to guarantee true test isolation,
    the DB tables are re-created each test run. Only one instance of PostgreSQL
    is created across all threads, thus causing major conflicts if concurrency
    > 1.

Functional testing
==================

Prerequisites
-------------

* Docker

  Deckhand requires Docker to run its functional tests. A basic installation
  guide for Docker for Ubuntu can be found
  `here <https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/>`_

* uwsgi

  Can be installed on Ubuntu systems via::

    sudo apt-get install uwsgi -y

Overview
--------
Deckhand uses `gabbi <https://github.com/cdent/gabbi>`_ as its functional
testing framework. Functional tests can be executed via::

    $ tox -e functional-dev

You can also run a subset of tests via a regex::

    $ tox -e functional-dev -- gabbi.suitemaker.test_gabbi_document-crud-success-multi-bucket

The command executes ``tools/functional-tests.sh`` which:

    1) Launches Postgresql inside a Docker container.
    2) Sets up a basic Deckhand configuration file that uses Postgresql
       in its ``oslo_db`` connection string.
    3) Sets up a custom policy file with very liberal permissions so that
       gabbi can talk to Deckhand without having to authenticate against
       Keystone and pass an admin token to Deckhand.
    4) Instantiates Deckhand via ``uwisgi``.
    5) Calls gabbi which runs a battery of functional tests.
    6) An HTML report that visualizes the result of the test run is output to
       ``results/index.html``.

Note that functional tests can be run concurrently; the flags ``--workers``
and ``--threads`` which are passed to ``uwsgi`` can be > 1.

.. todo::

  At this time, there are no functional tests for policy enforcement
  verification. Negative tests will be added at a later date to confirm that
  a 403 Forbidden is raised for each endpoint that does policy enforcement
  absent necessary permissions.

CICD
----
Since it is important to validate the Deckhand image itself, CICD:

* Generates the Deckhand image from the new patchset
* Runs functional tests against the just-produced Deckhand image

Deckhand uses the same script -- ``tools/functional-tests.sh`` -- for CICD
testing. To test Deckhand against a containerized image, run, for example:

::

  export DECKHAND_IMAGE=quay.io/airshipit/deckhand:latest-ubuntu_bionic
  tox -e functional-dev

Which will result in the following script output:

::

  Running Deckhand via Docker
  + sleep 5
  + sudo docker run --rm --net=host -p 9000:9000 -v /opt/stack/deckhand/tmp.oBJ6XScFgC:/etc/deckhand quay.io/airshipit/deckhand:latest-ubuntu_bionic

.. warning::

  For testing dev changes, it is **not** recommended to follow this approach,
  as the most up-to-date code is located in the repository itself. Running tests
  against a remote image will likely result in false positives.

Troubleshooting
===============

* For any errors related to ``tox``:

  Ensure that ``tox`` is installed::

    $ sudo apt-get install tox -y

* For any errors related to running ``tox -e py35``:

  Ensure that ``python3-dev`` is installed::

    $ sudo apt-get install python3-dev -y
