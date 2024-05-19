#!/bin/bash
echo "Setting up virtual environment ..."
python -m venv venv

echo "Install requirements ..."
venv/bin/pip install -r requirements.txt
venv/bin/pip install cx_Freeze

echo "Building binaries ..."
venv/bin/python setup.py build
