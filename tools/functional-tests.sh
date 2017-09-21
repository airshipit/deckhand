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

cat <<EOCONF > $CONF_DIR/deckhand.conf
[DEFAULT]
debug = true
log_config_append = $CONF_DIR/logging.conf
log_file = deckhand.log
log_dir = .
use_stderr = true

[oslo_policy]
policy_file = policy.yaml

[barbican]

[database]
connection = $DATABASE_URL

[keystone_authtoken]
EOCONF

    echo $CONF_DIR/deckhand.conf 1>&2
    cat $CONF_DIR/deckhand.conf 1>&2

    log_section Starting server
    rm -f deckhand.log
}

function gen_policy {
    log_section Creating policy file with liberal permissions

    oslopolicy-sample-generator --config-file=etc/deckhand/policy-generator.conf

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

set +e
posargs=$@
if [ ${#posargs} -ge 1 ]; then
    ostestr --concurrency 1 --regex $1
else
    ostestr --concurrency 1
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
