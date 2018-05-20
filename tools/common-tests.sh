#!/usr/bin/env bash

function log_section {
    set +x
    echo 1>&2
    echo 1>&2
    echo === $* === 1>&2
    set -x
}


function deploy_postgre {
    #######################################
    # Deploy an ephemeral PostgreSQL DB.
    # Globals:
    #   POSTGRES_ID
    #   POSTGRES_IP
    # Arguments:
    #   None
    # Returns:
    #   None
    #######################################
    set -xe

    # TODO(felipemonteiro): Use OSH PostgreSQL chart.
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

    echo $POSTGRES_IP
}


function gen_config {
    #######################################
    # Generate sample configuration file
    # Globals:
    #   CONF_DIR
    #   DECKHAND_TEST_URL
    #   DATABASE_URL
    #   DECKHAND_CONFIG_DIR
    # Arguments:
    #   disable_keystone: true or false
    #   Deckhand test URL: URL to Deckhand wsgi server
    # Returns:
    #   None
    #######################################
    set -xe

    log_section "Creating config directory and test deckhand.conf"

    CONF_DIR=$(mktemp -d -p $(pwd))
    sudo chmod 777 -R $CONF_DIR

    local disable_keystone=$1
    export DECKHAND_TEST_URL=$2
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

    if $disable_keystone; then
        log_section "Toggling development_mode on to disable Keystone authentication."
        sed -i -e 's/development_mode = false/development_mode = true/g' $conf_file
    fi

    echo $conf_file 1>&2
    cat $conf_file 1>&2

    echo $CONF_DIR/logging.conf 1>&2
    cat $CONF_DIR/logging.conf 1>&2
}


function gen_paste {
    #######################################
    # Generate sample paste.ini file
    # Globals:
    #   CONF_DIR
    # Arguments:
    #   disable_keystone: true or false
    # Returns:
    #   None
    #######################################
    set -xe

    local disable_keystone=$1

    if $disable_keystone; then
        log_section "Using noauth-paste.ini to disable Keystone authentication."
        cp etc/deckhand/noauth-paste.ini $CONF_DIR/noauth-paste.ini
    else
        cp etc/deckhand/deckhand-paste.ini $CONF_DIR/deckhand-paste.ini
    fi
}
