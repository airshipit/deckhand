========
Deckhand
========

Deckhand is a document-based configuration storage service built with
auditability and validation in mind.

Core Responsibilities
=====================

* layering - helps reduce duplication in configuration while maintaining
  auditability across many sites
* substitution - provides separation between secret data and other
  configuration data, while allowing a simple interface for clients
* revision history - improves auditability and enables services to provide
  functional validation of a well-defined collection of documents that are
  meant to operate together
* validation - allows services to implement and register different kinds of
  validations and report errors

Getting Started
===============

To generate a configuration file automatically::

    $ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Copy the config file to a directory discoverably by ``oslo.conf``::

    $ cp etc/deckhand/deckhand.conf.sample ~/deckhand.conf

To setup an in-memory database for testing:

.. code-block:: ini

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = sqlite:///:memory:

To run locally in a development environment::

    $ sudo pip install uwsgi
    $ virtualenv -p python3 /var/tmp/deckhand
    $ . /var/tmp/deckhand/bin/activate
    $ sudo pip install .
    $ sudo python setup.py install
    $ uwsgi --ini uwsgi.ini

Testing
-------

Automated Testing
^^^^^^^^^^^^^^^^^

To run unit tests using sqlite, execute:

::

    $ tox -epy27
    $ tox -epy35

against a py27- or py35-backed environment, respectively. To run individual
unit tests, run:

::

    $ tox -e py27 -- deckhand.tests.unit.db.test_revisions

for example.

To run unit tests using postgresql, execute:

::

    $ tox -epy27-postgresql
    $ tox -epy35-postgresql

To run functional tests:

::

    $ tox -e functional

You can also run a subset of tests via a regex:

::

    $ tox -e functional -- gabbi.suitemaker.test_gabbi_document-crud-success-multi-bucket

Manual Testing
^^^^^^^^^^^^^^

Document creation can be tested locally using (from root deckhand directory):

.. code-block:: console

    $ curl -i -X PUT localhost:9000/api/v1.0/bucket/{bucket_name}/documents \
         -H "Content-Type: application/x-yaml" \
         --data-binary "@deckhand/tests/unit/resources/sample_document.yaml"

    # revision_id copy/pasted from previous response.
    $ curl -i -X GET localhost:9000/api/v1.0/revisions/1
