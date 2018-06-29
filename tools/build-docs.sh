#!/usr/bin/env bash

# Builds documentation and generates documentation diagrams from .uml
# files. Must be run from root project directory.

set -ex
rm -rf doc/build
rm -rf releasenotes/build
sphinx-build -W -b html doc/source doc/build/html
python -m plantuml doc/source/diagrams/*.uml
mv doc/source/diagrams/*.png doc/source/images
