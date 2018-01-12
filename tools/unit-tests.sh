#!/usr/bin/env bash

# Script for setting up temporary PostgreSQL database for testing unit tests
# against. Requires Docker CE (at least) to be executed. Fallback in case
# `pifpaf` fails.

function cleanup {
    sudo docker stop $POSTGRES_ID
}

trap cleanup EXIT


POSTGRES_ID=$(
    sudo docker run \
        --detach \
        --publish :5432 \
        -e POSTGRES_DB=deckhand \
        -e POSTGRES_USER=$(whoami) \
        -e POSTGRES_PASSWORD=password \
            postgres:9.5
)

POSTGRES_IP=$(
    sudo docker inspect \
        --format='{{ .NetworkSettings.Networks.bridge.IPAddress }}' \
            $POSTGRES_ID
)

# Used by unit tests to interact with DB.
export DATABASE_URL=postgresql+psycopg2://$(whoami):password@$POSTGRES_IP:5432/deckhand

set -e
posargs=$@
if [ ${#posargs} -ge 1 ]; then
    ostestr --concurrency 1 --regex ${posargs}
else
    ostestr --concurrency 1
fi
set +e
