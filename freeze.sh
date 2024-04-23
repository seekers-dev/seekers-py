#!/bin/bash

echo "Hello from the seekers community! cx_Freeze helper 24.4.18"

usage() {
  echo "Usage: $0 [-i|-s|-c|-t|-h]" 1>&2
}

install_requirements() {
  echo "Install requirements ..."
  python -m venv venv
  venv/bin/pip install -r requirements.txt
  venv/bin/pip install cx_Freeze
}

build_seekers() {
  echo "Building seekers ..."
  venv/bin/cxfreeze -c run_seekers.py --target-dir dist/seekers --include-files config.ini
}

build_client() {
  echo "Building client ..."
  venv/bin/cxfreeze -c run_client.py --target-dir dist/client --include-files config.ini
}

test() {
  echo "Testing build ..."
  dist/run_seekers examples/ai-decide.py examples/ai-simple.py
}

[ $# -eq 0 ] && usage
while getopts ":isct" arg; do
    case $arg in
        i)
            install_requirements
            ;;
        s)
            build_seekers
            ;;
        c)
            build_client
            ;;
        t)
            test
            ;;
        *)
            usage
            ;;
    esac
done
