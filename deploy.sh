#!/bin/bash

echo "Creating python archives ..."
zip -r seekers-linux-stubs.zip ./seekers/api
zip -r seekers-linux.zip ./*

echo "Install additional build requirements ..."
venv/bin/pip install cx_Freeze

echo "Building binaries ..."
venv/bin/python setup.py build

echo "Creating native archives ..."
zip -r seekers-linux-bin.zip ./build
