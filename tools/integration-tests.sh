#!/usr/bin/env bash

# Script intended for running Deckhand integration tests, where integration
# is defined as the interaction between Deckhand and Keystone and Barbican.
# Installation dependency is openstack-helm-infra.
#
# USAGE: ./tools/integration-tests.sh <test-regex>

# TODO(fmontei): Use Ansible for all this.
# NOTE(fmontei): May have to automate the following installation guide for CI:
# https://docs.openstack.org/openstack-helm/latest/install/developer/requirements-and-host-config.html#host-configuration

set -xe

DECKHAND_IMAGE=${DECKHAND_IMAGE:-quay.io/attcomdev/deckhand:latest}

CURRENT_DIR="$(pwd)"
: ${OSH_INFRA_PATH:="../openstack-helm-infra"}
: ${OSH_PATH:="../openstack-helm"}


function cleanup_osh {
    set -xe

    if [ -n "command -v kubectl" ]; then
        kubectl delete namespace openstack
        kubectl delete namespace ucp
    fi

    sudo systemctl disable kubelet --now
    sudo systemctl stop kubelet

    if [ -n "command -v docker" ]; then
        sudo docker ps -aq | xargs -L1 -P16 sudo docker rm -f
    fi

    sudo rm -rf /var/lib/openstack-helm
}


function cleanup_deckhand {
    set +e

    if [ -n "$POSTGRES_ID" ]; then
        sudo docker stop $POSTGRES_ID
    fi

    if [ -n "$DECKHAND_ID" ]; then
        sudo docker stop $DECKHAND_ID
    fi

    rm -rf $CONF_DIR
}


function deploy_barbican {
    set -xe

    # Pull images and lint chart
    make pull-images barbican

    # Deploy command
    helm upgrade --install barbican ./barbican \
        --namespace=openstack

    # Wait for deploy
    ./tools/deployment/common/wait-for-pods.sh openstack

    # Validate deployment info
    helm status barbican
}


function deploy_osh_keystone_barbican {
    set -xe

    trap cleanup_osh EXIT

    if [ ! -d "$OSH_INFRA_PATH" ]; then
        git clone https://git.openstack.org/openstack/openstack-helm-infra.git ../openstack-helm-infra
    fi

    if [ ! -d "$OSH_PATH" ]; then
        git clone https://git.openstack.org/openstack/openstack-helm.git ../openstack-helm
    fi

    cd ${OSH_INFRA_PATH}
    # NOTE(fmontei): setup-host already sets up required host dependencies.
    make dev-deploy setup-host
    make dev-deploy k8s

    # NOTE(fmontei): Use this version because newer versions might
    # be slightly different in terms of test syntax in YAML files.
    sudo -H -E pip install gabbi==1.35.1

    cd ${OSH_PATH}
    # Setup clients on the host and assemble the charts¶
    ./tools/deployment/developer/common/020-setup-client.sh
    # Deploy the ingress controller
    ./tools/deployment/developer/common/030-ingress.sh
    # Deploy NFS Provisioner
    ./tools/deployment/developer/nfs/040-nfs-provisioner.sh
    # Deploy MariaDB
    ./tools/deployment/developer/nfs/050-mariadb.sh
    # Deploy RabbitMQ
    ./tools/deployment/developer/nfs/060-rabbitmq.sh
    # Deploy Memcached
    ./tools/deployment/developer/nfs/070-memcached.sh
    # Deploy Keystone
    ./tools/deployment/developer/nfs/080-keystone.sh

    deploy_barbican
}


function deploy_deckhand {
    set -xe

    trap cleanup_deckhand EXIT

    export OS_CLOUD=openstack_helm

    cd ${CURRENT_DIR}

    # TODO(fmontei): Use Keystone bootstrap override instead.
    interfaces=("admin" "public" "internal")
    deckhand_endpoint="http://127.0.0.1:9000"

    if [ -z "$( openstack service list --format value | grep deckhand )" ]; then
        openstack service create --enable --name deckhand deckhand
    fi

    for iface in ${interfaces[@]}; do
        if [ -z "$( openstack endpoint list --format value | grep deckhand | grep $iface )" ]; then
            openstack endpoint create --enable \
                --region RegionOne \
                deckhand $iface $deckhand_endpoint/api/v1.0
        fi
    done

    openstack service list | grep deckhand
    openstack endpoint list | grep deckhand

    gen_config false $deckhand_endpoint
    gen_paste false

    # NOTE(fmontei): Generate an admin token instead of hacking a policy
    # file with no permissions to test authN as well as authZ.
    export TEST_AUTH_TOKEN=$( openstack token issue --format value -c id )
    local test_barbican_url=$( openstack endpoint list --format value | grep barbican | grep public | awk '{print $7}' )

    if [[ $test_barbican_url == */ ]]; then
        test_barbican_url=$( echo $test_barbican_url | sed 's/.$//' )
    fi

    export TEST_BARBICAN_URL=$test_barbican_url

    log_section "Running Deckhand via Docker"
    sudo docker run \
        --rm \
        --net=host \
        -v $CONF_DIR:/etc/deckhand \
        $DECKHAND_IMAGE alembic upgrade head &
    sudo docker run \
        --rm \
        --net=host \
        -p 9000:9000 \
        -v $CONF_DIR:/etc/deckhand \
        $DECKHAND_IMAGE server &

    # Give the server a chance to come up. Better to poll a health check.
    sleep 5

    DECKHAND_ID=$(sudo docker ps | grep deckhand | awk '{print $1}')
    echo $DECKHAND_ID
}


function run_tests {
    set +e

    export DECKHAND_TEST_DIR=${CURRENT_DIR}/deckhand/tests/integration/gabbits

    posargs=$@
    if [ ${#posargs} -ge 1 ]; then
        py.test -k $1 -svx ${CURRENT_DIR}/deckhand/tests/common/test_gabbi.py
    else
        py.test -svx ${CURRENT_DIR}/deckhand/tests/common/test_gabbi.py
    fi
    TEST_STATUS=$?

    set -e

    if [ "x$TEST_STATUS" = "x0" ]; then
        log_section Done SUCCESS
    else
        log_section Done FAILURE
        exit $TEST_STATUS
    fi
}


source ${CURRENT_DIR}/tools/common-tests.sh

# Clone openstack-helm-infra and setup host and k8s.
deploy_osh_keystone_barbican

# Deploy PostgreSQL and Deckhand.
deploy_postgresql
deploy_deckhand

run_tests "$@"
