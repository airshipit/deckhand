#!/usr/bin/env bash

# Script intended for running Deckhand functional tests via gabbi. Requires
# Docker CE (at least) to run.

# Meant for capturing output of Deckhand image. This requires that logging
# in the image be set up to pipe everything out to stdout/stderr.
STDOUT=$(mktemp)
# NOTE(fmontei): `DECKHAND_IMAGE` should only be specified if the desire is to
# run Deckhand functional tests against a specific Deckhand image, which is
# useful for CICD (as validating the image is vital). However, if the
# `DECKHAND_IMAGE` is not specified, then this implies that the most current
# version of the code should be used, which is in the repo itself.
DECKHAND_IMAGE=${DECKHAND_IMAGE:-}

function log_section {
    set +x
    echo 1>&2
    echo 1>&2
    echo === $* === 1>&2
    set -x
}

set -ex

function cleanup {
    sudo docker stop $POSTGRES_ID
    if [ -n "$DECKHAND_ID" ]; then
        sudo docker stop $DECKHAND_ID
    fi
    rm -rf $CONF_DIR

    if [ -z "$DECKHAND_IMAGE" ]; then
        # Kill all processes and child processes (for example, if workers > 1)
        # if using uwsgi only.
        PGID=$(ps -o comm -o pgid | grep uwsgi | grep -o [0-9]* | head -n 1)
        setsid kill -- -$PGID
    fi
}


trap cleanup EXIT


POSTGRES_ID=$(
    sudo docker run \
        --detach \
        --publish :5432 \
        -e POSTGRES_DB=deckhand \
        -e POSTGRES_USER=deckhand \
        -e POSTGRES_PASSWORD=password \
            postgres:9.5
)

POSTGRES_IP=$(
    sudo docker inspect \
        --format='{{ .NetworkSettings.Networks.bridge.IPAddress }}' \
            $POSTGRES_ID
)


CONF_DIR=$(mktemp -d -p $(pwd))
sudo chmod 777 -R $CONF_DIR

function gen_config {
    log_section Creating config file

    export DECKHAND_TEST_URL=http://localhost:9000
    export DATABASE_URL=postgresql+psycopg2://deckhand:password@$POSTGRES_IP:5432/deckhand
    # Used by Deckhand's initialization script to search for config files.
    export DECKHAND_CONFIG_DIR=$CONF_DIR

    cp etc/deckhand/logging.conf.sample $CONF_DIR/logging.conf

# Create a logging config file to dump everything to stdout/stderr.
cat <<EOCONF > $CONF_DIR/logging.conf
[loggers]
keys = root, deckhand, error

[handlers]
keys = null, stderr, stdout

[formatters]
keys = simple, context

[logger_deckhand]
level = DEBUG
handlers = stdout
qualname = deckhand

[logger_error]
level = ERROR
handlers = stderr

[logger_root]
level = WARNING
handlers = null

[handler_stderr]
class = StreamHandler
args = (sys.stderr,)
formatter = context

[handler_stdout]
class = StreamHandler
args = (sys.stdout,)
formatter = context

[handler_null]
class = logging.NullHandler
formatter = context
args = ()

[formatter_context]
class = oslo_log.formatters.ContextFormatter

[formatter_simple]
format=%(asctime)s.%(msecs)03d %(process)d %(levelname)s: %(message)s
EOCONF

# Create a Deckhand config file with bare minimum options.
cat <<EOCONF > $CONF_DIR/deckhand.conf
[DEFAULT]
debug = true
publish_errors = true
use_stderr = true
# NOTE: allow_anonymous_access allows these functional tests to get around
# Keystone authentication, but the context that is provided has zero privileges
# so we must also override the policy file for authorization to pass.
allow_anonymous_access = true

[oslo_policy]
policy_file = policy.yaml

[barbican]

[database]
connection = $DATABASE_URL

[keystone_authtoken]
# Populate keystone_authtoken with values like the following should Keystone
# integration be needed here.
# project_domain_name = Default
# project_name = admin
# user_domain_name = Default
# password = devstack
# username = admin
# auth_url = http://127.0.0.1/identity
# auth_type = password
EOCONF

# Only set up logging if running Deckhand via uwsgi. The container already has
# values for logging.
if [ -z "$DECKHAND_IMAGE" ]; then
    sed '1 a log_config_append = '"$CONF_DIR"'/logging.conf' $CONF_DIR/deckhand.conf
fi

# Only set up logging if running Deckhand via uwsgi. The container already has
# values for logging.
if [ -z "$DECKHAND_IMAGE" ]; then
    sed '1 a log_config_append = '"$CONF_DIR"'/logging.conf' $CONF_DIR/deckhand.conf
fi

    echo $CONF_DIR/deckhand.conf 1>&2
    cat $CONF_DIR/deckhand.conf 1>&2

    echo $CONF_DIR/logging.conf 1>&2
    cat $CONF_DIR/logging.conf 1>&2

    log_section Starting server
}

function gen_paste {
    log_section Creating paste config without [filter:authtoken]
    # NOTE(fmontei): Since this script does not currently support Keystone
    # integration, we remove ``filter:authtoken`` from the ``deckhand_api``
    # pipeline to avoid any kind of auth issues.
    sed 's/authtoken api/api/' etc/deckhand/deckhand-paste.ini &> $CONF_DIR/deckhand-paste.ini
}

function gen_policy {
    log_section Creating policy file with liberal permissions

    policy_file='etc/deckhand/policy.yaml.sample'
    policy_pattern="deckhand\:"

    touch $CONF_DIR/policy.yaml

    sed -n "/$policy_pattern/p" "$policy_file" \
        | sed 's/^../\"/' \
        | sed 's/rule\:[A-Za-z\_\-]*/@/' > $CONF_DIR/policy.yaml

    echo $CONF_DIR/'policy.yaml' 1>&2
    cat $CONF_DIR/'policy.yaml' 1>&2
}

gen_config
gen_paste
gen_policy

ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -z "$DECKHAND_IMAGE" ]; then
    log_section "Running Deckhand via uwsgi"

    alembic upgrade head
    # NOTE(fmontei): Deckhand's database is not configured to work with
    # multiprocessing. Currently there is a data race on acquiring shared
    # SQLAlchemy engine pooled connection strings when workers > 1. As a
    # workaround, we use multiple threads but only 1 worker. For more
    # information, see: https://github.com/att-comdev/deckhand/issues/20
    export DECKHAND_API_WORKERS=1
    export DECKHAND_API_THREADS=4
    source $ROOTDIR/../entrypoint.sh &
    sleep 5
else
    log_section "Running Deckhand via Docker"
    sudo docker run \
        --rm \
        --net=host \
        -v $CONF_DIR:/etc/deckhand \
        $DECKHAND_IMAGE alembic upgrade head &> $STDOUT
    sudo docker run \
        --rm \
        --net=host \
        -p 9000:9000 \
        -v $CONF_DIR:/etc/deckhand \
        $DECKHAND_IMAGE &> $STDOUT &
fi

# Give the server a chance to come up. Better to poll a health check.
sleep 5

DECKHAND_ID=$(sudo docker ps | grep deckhand | awk '{print $1}')
echo $DECKHAND_ID

log_section Running tests

# Create folder for saving HTML test results.
if [ ! -d $ROOTDIR/results ]; then
    mkdir $ROOTDIR/results
fi

set +e
posargs=$@
if [ ${#posargs} -ge 1 ]; then
    py.test -k $1 -svx $( dirname $ROOTDIR )/deckhand/tests/functional/test_gabbi.py --html=results/index.html
else
    py.test -svx $( dirname $ROOTDIR )/deckhand/tests/functional/test_gabbi.py --html=results/index.html
fi
TEST_STATUS=$?
set -e

if [ "x$TEST_STATUS" = "x0" ]; then
    log_section Done SUCCESS
else
    log_section Deckhand Server Log
    cat $STDOUT
    log_section Done FAILURE
    exit $TEST_STATUS
fi
