Getting Started
===============

Pre-requisites
--------------

* tox

  To install tox run::

    $ [sudo] apt-get install tox

* PostgreSQL

  Deckhand only supports PostgreSQL. Install it by running::

    $ [sudo] apt-get update
    $ [sudo] apt-get install postgresql postgresql-contrib

Quickstart
----------

SQLite
^^^^^^

The guide below provides details on how to run Deckhand quickly using
SQLite.

`Docker`_ can be used to quickly instantiate the Deckhand image. After
installing `Docker`_, create a basic configuration file::

    $ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Move the sample configuration file into a desired directory
(i.e. ``$CONF_DIR``).

Set the database string in the configuration file to ``sqlite://``

.. code-block:: ini

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = sqlite://

Finally, run Deckhand via Docker::

    $ [sudo] docker run --rm \
        --net=host \
        -p 9000:9000 \
        -v $CONF_DIR:/etc/deckhand \
        quay.io/attcomdev/deckhand:latest

PostgreSQL
^^^^^^^^^^

The guide below provides details on how to run Deckhand quickly using
PostgreSQL.

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

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824

Finally, run Deckhand via Docker::

    $ [sudo] docker run --rm \
        --net=host \
        -p 9000:9000 \
        -v $CONF_DIR:/etc/deckhand \
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

    $ [sudo] pip install uwsgi
    $ virtualenv -p python3 /var/tmp/deckhand
    $ . /var/tmp/deckhand/bin/activate
    $ pip install -r requirements.txt -r test-requirements.txt
    $ python setup.py install

Afterward, create a sample configuration file automatically::

    $ tox -e genconfig

Resulting deckhand.conf.sample file is output to
:path:etc/deckhand/deckhand.conf.sample

Create the directory ``/etc/deckhand`` and copy the config file there::

    $ [sudo] cp etc/deckhand/deckhand.conf.sample /etc/deckhand/deckhand.conf

To specify an alternative directory for the config file, run::

    $ export DECKHAND_CONFIG_DIR=<PATH>
    $ [sudo] cp etc/deckhand/deckhand.conf.sample ${DECKHAND_CONFIG_DIR}/deckhand.conf

To conveniently create an ephemeral PostgreSQL DB run::

    $ eval `pifpaf run postgresql`

Retrieve the environment variable which contains connection information::

    $ export | grep PIFPAF_POSTGRESQL_URL
    declare -x PIFPAF_POSTGRESQL_URL="postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824"

Substitute the connection information into the config file in
``${DECKHAND_CONFIG_DIR}``::

    [database]

    #
    # From oslo.db
    #

    # The SQLAlchemy connection string to use to connect to the database.
    # (string value)
    connection = postgresql://localhost/postgres?host=/tmp/tmpsg6tn3l9&port=9824

Finally, run Deckhand::

    $ chmod +x entrypoint.sh
    $ ./entrypoint.sh

To kill the ephemeral DB afterward::

    $ pifpaf_stop

Development Utilities
---------------------

Deckhand comes equipped with many utilities useful for developers, such as
unit test or linting jobs.

Many of these commands require that ``tox`` be installed. To do so, run::

  $ pip3 install tox

To run the Python linter, execute::

  $ tox -e pep8

To run unit tests, execute::

  $ tox -e py35

To run the test coverage job::

  $ tox -e coverage

To run security checks via `Bandit`_ execute::

  $ tox -e bandit

To build all Deckhand charts, execute::

  $ make charts

To generate sample configuration and policy files needed for Deckhand
deployment, execute (respectively)::

  $ tox -e genconfig
  $ tox -e genpolicy

.. _Bandit: https://github.com/openstack/bandit

Troubleshooting
---------------

The error messages are included in bullets below and tips to resolution are
included beneath each bullet.

* "FileNotFoundError: [Errno 2] No such file or directory: '/etc/deckhand/api-paste.ini'"

  Reason: this means that Deckhand is trying to instantiate the server but
  failing to do so because it can't find an essential configuration file.

  Solution::

    $ cp etc/deckhand/deckhand.conf.sample /etc/deckhand/deckhand.conf

  This copies the sample Deckhand configuration file to the appropriate
  directory.

* For any errors related to ``tox``:

  Ensure that ``tox`` is installed::

    $ [sudo] apt-get install tox -y

* For any errors related to running ``tox -e py35``:

  Ensure that ``python3-dev`` is installed::

    $ [sudo] apt-get install python3-dev -y

* For any errors related to running ``tox -e py27``:

  Ensure that ``python3-dev`` is installed::

    $ [sudo] apt-get install python-dev -y
