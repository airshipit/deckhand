========
Deckhand
========

Deckhand is a storage service for YAML-based configuration documents, which are
managed through version control and automatically validated. Deckhand provides
users with a variety of different document types that describe complex
configurations using the features listed below.

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

Pre-requisites
--------------

* tox

  To install tox run::

    $ sudo apt-get install tox

* PostgreSQL

  Deckhand only supports PostgreSQL. Install it by running::

    $ sudo apt-get update
    $ sudo apt-get install postgresql postgresql-contrib

Quick Start
-----------

`Docker`_ can be used to quickly instantiate the Deckhand image. After
installing `Docker`_, create a basic configuration file::

    $ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Move the sample configuration file into a desired directory
(i.e. ``$CONF_DIR``).

At a minimum the ``[database].connection`` config option must be set.
Provide it with a PostgreSQL database connection. Or to conveniently create an
ephemeral PostgreSQL DB run::

    $ eval `pifpaf run postgresql`

Substitute the connection information (which can be retrieved by running
``export | grep PIFPAF_POSTGRESQL_URL``) into the config file inside
``etc/deckhand/deckhand.conf.sample``::

.. code-block:: ini

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824

Finally, run Deckhand::

    $ [sudo] docker run --rm \
        --net=host \
        -p 9000:9000 \
        -v $CONF_DIR:/etc/deckhand
        quay.io/attcomdev/deckhand:latest

To kill the ephemeral DB afterward::

    $ pifpaf_stop

.. _Docker: https://docs.docker.com/install/

Manual Installation
-------------------

.. note::

    The commands below assume that they are being executed from the root
    Deckhand directory.

Install dependencies needed to spin up Deckhand via ``uwsgi``::

    $ sudo pip install uwsgi
    $ virtualenv -p python3 /var/tmp/deckhand
    $ . /var/tmp/deckhand/bin/activate
    $ pip install -r requirements.txt test-requirements.txt
    $ python setup.py install

Afterward, create a sample configuration file automatically::

    $ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Create the directory ``/etc/deckhand`` and copy the config file there::

    $ [sudo] cp etc/deckhand/deckhand.conf.sample /etc/deckhand/deckhand.conf

To specify an alternative directory for the config file, run::

    $ export OS_DECKHAND_CONFIG_DIR=<PATH>
    $ [sudo] cp etc/deckhand/deckhand.conf.sample ${OS_DECKHAND_CONFIG_DIR}/deckhand.conf

To conveniently create an ephemeral PostgreSQL DB run::

    $ eval `pifpaf run postgresql`

Retrieve the environment variable which contains connection information::

    $ export | grep PIFPAF_POSTGRESQL_URL
    declare -x PIFPAF_POSTGRESQL_URL="postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824"

Substitute the connection information into the config file in
``${OS_DECKHAND_CONFIG_DIR}``::

.. code-block:: ini

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824

Finally, run Deckhand::

    $ uwsgi --ini wsgi.ini

To kill the ephemeral DB afterward::

    $ pifpaf_stop

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

To run functional tests:

::

    $ tox -e functional

You can also run a subset of tests via a regex:

::

    $ tox -e functional -- gabbi.suitemaker.test_gabbi_document-crud-success-multi-bucket

Intgration Points
=================

Deckhand has the following integration points:

  * `Keystone (OpenStack Identity service) <https://github.com/openstack/keystone>`_
    provides authentication and support for role based authorization.
  * `PostgreSQL <https://www.postgresql.org>`_ is used to persist information
    to correlate workflows with users and history of workflow commands.

  .. note::

    Currently, other database backends are not supported.

Though, being a low-level service, has many other UCP services that integrate
with it, including:

  * `Drydock <https://github.com/att-comdev/drydock>`_ is orchestrated by
    Shipyard to perform bare metal node provisioning.
  * `Promenade <https://github.com/att-comdev/promenade>`_ is indirectly
    orchestrated by Shipyard to configure and join Kubernetes nodes.
  * `Armada <https://github.com/att-comdev/armada>`_ is orchestrated by
    Shipyard to deploy and test Kubernetes workloads.

Further Reading
===============

`Undercloud Platform (UCP) <https://github.com/att-comdev/ucp-integration>`_.
