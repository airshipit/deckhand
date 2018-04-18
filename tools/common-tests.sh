#!/usr/bin/env bash

function log_section {
    set +x
    echo 1>&2
    echo 1>&2
    echo === $* === 1>&2
    set -x
}


function deploy_postgre {
    set -xe

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
}


function gen_config {
    set -xe

    log_section "Creating config directory and test deckhand.conf"

    CONF_DIR=$(mktemp -d -p $(pwd))
    sudo chmod 777 -R $CONF_DIR

    export DECKHAND_TEST_URL=$1
    export DATABASE_URL=postgresql+psycopg2://deckhand:password@$POSTGRES_IP:5432/deckhand
    # Used by Deckhand's initialization script to search for config files.
    export DECKHAND_CONFIG_DIR=$CONF_DIR

    local conf_file=${CONF_DIR}/deckhand.conf

    cp etc/deckhand/logging.conf.sample $CONF_DIR/logging.conf
    envsubst '${DATABASE_URL}' < deckhand/tests/deckhand.conf.test > $conf_file

    # Only set up logging if running Deckhand via uwsgi. The container already has
    # values for logging.
    if [ -z "$DECKHAND_IMAGE" ]; then
        sed '1 a log_config_append = '"$CONF_DIR"'/logging.conf' $conf_file
    fi

    echo $conf_file 1>&2
    cat $conf_file 1>&2

    echo $CONF_DIR/logging.conf 1>&2
    cat $CONF_DIR/logging.conf 1>&2
}


function gen_paste {
    set -xe

    local disable_keystone=$1

    if $disable_keystone; then
        log_section Disabling Keystone authentication.
        sed 's/authtoken api/api/' etc/deckhand/deckhand-paste.ini &> $CONF_DIR/deckhand-paste.ini
    else
        cp etc/deckhand/deckhand-paste.ini $CONF_DIR/deckhand-paste.ini
    fi
}


function gen_policy {
    set -xe

    log_section "Creating policy file with liberal permissions"

    policy_file='etc/deckhand/policy.yaml.sample'
    policy_pattern="deckhand\:"

    touch $CONF_DIR/policy.yaml

    sed -n "/$policy_pattern/p" "$policy_file" \
        | sed 's/^../\"/' \
        | sed 's/rule\:[A-Za-z\_\-]*/@/' > $CONF_DIR/policy.yaml

    echo $CONF_DIR/'policy.yaml' 1>&2
    cat $CONF_DIR/'policy.yaml' 1>&2
}
