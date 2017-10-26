#!/usr/bin/env bash

function log_section {
    set +x
    echo 1>&2
    echo 1>&2
    echo === $* === 1>&2
    set -x
}

set -ex


log_section Starting Postgres
POSTGRES_ID=$(
    sudo docker run \
        --detach \
        --publish :5432 \
        -e POSTGRES_DB=deckhand \
        -e POSTGRES_USER=deckhand \
        -e POSTGRES_PASSWORD=password \
            postgres:9.5
)

function cleanup {
    sudo docker stop $POSTGRES_ID
    kill %1
}

trap cleanup EXIT

POSTGRES_IP=$(
    sudo docker inspect \
        --format='{{ .NetworkSettings.Networks.bridge.IPAddress }}' \
            $POSTGRES_ID
)

CONF_DIR=$(mktemp -d)

function gen_config {
    log_section Creating config file

    export DECKHAND_TEST_URL=http://localhost:9000
    export DATABASE_URL=postgresql+psycopg2://deckhand:password@$POSTGRES_IP:5432/deckhand
    # Used by Deckhand's initialization script to search for config files.
    export OS_DECKHAND_CONFIG_DIR=$CONF_DIR

    cp etc/deckhand/logging.conf.sample $CONF_DIR/logging.conf

# NOTE: allow_anonymous_access allows these functional tests to get around
# Keystone authentication, but the context that is provided has zero privileges
# so we must also override the policy file for authorization to pass.
cat <<EOCONF > $CONF_DIR/deckhand.conf
[DEFAULT]
debug = true
log_config_append = $CONF_DIR/logging.conf
log_file = deckhand.log
log_dir = .
use_stderr = true
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

    echo $CONF_DIR/deckhand.conf 1>&2
    cat $CONF_DIR/deckhand.conf 1>&2

    log_section Starting server
    rm -f deckhand.log
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

uwsgi \
    --http :9000 \
    -w deckhand.cmd \
    --callable deckhand_callable \
    --enable-threads \
    -L \
    --pyargv "--config-file $CONF_DIR/deckhand.conf" &

# Give the server a chance to come up.  Better to poll a health check.
sleep 5

log_section Running tests

ROOTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

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
    cat deckhand.log
    log_section Done FAILURE
    exit $TEST_STATUS
fi
