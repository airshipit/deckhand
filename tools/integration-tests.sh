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

CURRENT_DIR="$(pwd)"
: ${OSH_INFRA_PATH:="../openstack-helm-infra"}
: ${OSH_PATH:="../openstack-helm"}


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
    helm status barbican -n openstack
}


function deploy_osh_keystone_barbican {
    set -xe

    if [ ! -d "$OSH_INFRA_PATH" ]; then
        git clone https://git.openstack.org/openstack/openstack-helm-infra.git ../openstack-helm-infra
    fi

    if [ ! -d "$OSH_PATH" ]; then
        git clone https://git.openstack.org/openstack/openstack-helm.git ../openstack-helm
    fi

    cd ${OSH_INFRA_PATH}
    # git reset --hard ${BARBICAN_STABLE_COMMIT}
    # Deploy required packages
    ./tools/deployment/common/000-install-packages.sh
    ./tools/deployment/common/001-setup-apparmor-profiles.sh
    #
    cd ${OSH_PATH}
    # git reset --hard ${BARBICAN_STABLE_COMMIT}
    # Deploy required packages
    ./tools/deployment/common/install-packages.sh
    #
    # Deploy Kubernetes
    sudo modprobe br_netfilter
    ./tools/deployment/common/deploy-k8s.sh

    cd ${CURRENT_DIR}
    sudo -H -E pip install -r requirements-frozen.txt

    # remove systemd-resolved local stub dns from resolv.conf
    sudo sed -i.bkp '/^nameserver.*127.0.0.1/d
                     w /dev/stdout' /etc/resolv.conf
    # add external nameservers
    echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
    echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf
    cat /etc/resolv.conf

    cd ${OSH_PATH}
    # Setup clients on the host and assemble the charts
    ./tools/deployment/common/setup-client.sh
    # Deploy the ingress controller
    ./tools/deployment/component/common/ingress.sh
    # Deploy NFS Provisioner
    ./tools/deployment/component/nfs-provisioner/nfs-provisioner.sh
    # Deploy MariaDB
    ./tools/deployment/component/common/mariadb.sh
    # Deploy RabbitMQ
    ./tools/deployment/component/common/rabbitmq.sh
    # Deploy Memcached
    ./tools/deployment/component/common/memcached.sh
    # Deploy Keystone
    ./tools/deployment/component/keystone/keystone.sh

    deploy_barbican
}


function deploy_deckhand {
    set -xe

    export OS_CLOUD=openstack_helm

    cd ${CURRENT_DIR}

    # TODO(fmontei): Use Keystone bootstrap override instead.
    interfaces=("admin" "public" "internal")
    deckhand_endpoint="http://127.0.0.1:9000"

    if [ -z "$( openstack service list --format value 2>/dev/null | grep deckhand )" ]; then
        openstack service create --enable --name deckhand deckhand 2>/dev/null
    fi

    for iface in ${interfaces[@]}; do
        if [ -z "$( openstack endpoint list --format value 2>/dev/null | grep deckhand | grep $iface )" ]; then
            openstack endpoint create --enable \
                --region RegionOne \
                deckhand $iface $deckhand_endpoint/api/v1.0 \
                     2>/dev/null
        fi
    done

    openstack service list | grep deckhand
    openstack endpoint list | grep deckhand

    gen_config false $deckhand_endpoint
    gen_paste false

    log_section "Running Deckhand via uwsgi."

    source ${CURRENT_DIR}/entrypoint.sh alembic upgrade head &
    # Give time for migrations to complete.
    sleep 10

    source ${CURRENT_DIR}/entrypoint.sh server &
    # Give the server a chance to come up. Better to poll a health check.
    sleep 10

    # NOTE(fmontei): Generate an admin token instead of hacking a policy
    # file with no permissions to test authN as well as authZ.
    export TEST_AUTH_TOKEN=$( openstack token issue --format value -c id  2>/dev/null )
    local test_barbican_url=$( openstack endpoint list --format value  2>/dev/null | grep barbican | grep public | awk '{print $7}' )

    if [[ $test_barbican_url == */ ]]; then
        test_barbican_url=$( echo $test_barbican_url | sed 's/.$//' )
    fi

    export TEST_BARBICAN_URL=$test_barbican_url
}


function run_tests {
    set +e

    export DECKHAND_TEST_DIR=${CURRENT_DIR}/deckhand/tests/integration/gabbits

    posargs=$@
    if [ ${#posargs} -ge 1 ]; then
        stestr --test-path deckhand/tests/common/ run --verbose --serial --slowest --force-subunit-trace --color $1
    else
        stestr --test-path deckhand/tests/common/ run --verbose --serial --slowest --force-subunit-trace --color
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

export AIRSHIP_DECKHAND_DATABASE_URL=${PIFPAF_POSTGRESQL_URL}

# Clone openstack-helm-infra and setup host and k8s.
deploy_osh_keystone_barbican

# Deploy Deckhand.
deploy_deckhand

run_tests "$@"
