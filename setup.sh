#!/bin/bash

echo "Setting up virtual environment ..."
python -m venv venv

echo "Install requirements ..."
venv/bin/pip install -r requirements.txt

echo "Update submodule ..."
git submodule update --init --recursive --remote

echo "Compile proto files"
cd seekers-api || exit
bash compile.sh
cp -r api ../seekers