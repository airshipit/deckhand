..
    Copyright 2019 SUSE LLC

    Licensed under the Apache License, Version 2.0 (the "License"); you may
    not use this file except in compliance with the License. You may obtain
    a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    License for the specific language governing permissions and limitations
    under the License.


Multiple Distro Support
=======================

This project builds images for Deckhand component only. Currently, it
supports building images for ubuntu and opensuse ( leap 15.0 as base image).

By default, Ubuntu images are built and are published to public registry
server. Recently support for publishing opensuse image has been added.

If you need to build opensuse images locally, the following parameters
can be passed to the *make* command in deckhand repository's root
directory with *images* as target::

    DISTRO: opensuse_15
    DISTRO_BASE_IMAGE: "opensuse/leap:15.0"
    DOCKER_REGISTRY: { your_docker_registry }
    IMAGE_TAG: latest
    PUSH_IMAGE: false

Following is an example in command format to build and publish images locally.
Command is run in deckhand repository's root directory.

    make images DISTRO=opensuse_15 DOCKER_REGISTRY={ your_docker_registry} \
    IMAGE_TAG=latest PUSH_IMAGE=true


Following parameters need to be passed as environment/shell variable to make
command:

DISTRO
  parameter to identify distro specific Dockerfile, ubuntu_xenial (Default)

DISTRO_BASE_IMAGE
  parameter to use different base image other than what's
  used in DISTRO specific Dockerfile (optional)

DOCKER_REGISTRY
 parameter to specify local/internal docker registry if need
 to publish image (optional), quay.io (Default)

IMAGE_TAG
  tag to be used for image built, untagged (Default)

PUSH_IMAGE
  flag to indicate if images needs to be pushed to a docker
  registry, false (Default)

This work is done as per approved spec `multi_distro_support`_. Currently only image
building logic is enhanced to support multiple distro.


Adding New Distro Support
--------------------------

To add support for building images for a new distro, following steps can be
followed.

  #. Distro specific deckhand image can be built and tested locally first.

  #. Add distro specific Dockerfile which will have steps to include necessary
     packages and run environment configuration. Use existing Dockerfile as sample
     to identify needed packages and environment information.

  #. New dockerfile can be named as Dockefile.{DISTRO} where DISTRO is expected to be
     distro identifier which is passed to makefile.

  #. Respective dockerfile needs to be placed in {deckahnd_repo}/images/deckhand/

  #. Add check, gate, and post jobs for building, testing and publishing images. These
     entries need to be added in {deckhand_repo}/.zuul.yaml file. You may refer to
     existing zuul file to opensuse support to understand its usage pattern.

  #. Add any relevant information to this document.


.. _multi_distro_support: https://airship-specs.readthedocs.io/en/latest/specs/approved/airship_multi_linux_distros.html
