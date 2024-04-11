#!/bin/bash

echo "Hello from the seekers community! cx_Freeze helper 24.3.15"

usage() {
  echo "Usage: $0 [-b|-s]" 1>&2
}

build() {
  echo "Building projekt ..."
  pip install -r requirements.txt
  pip install cx_Freeze
  cxfreeze -c run_seekers.py --target-dir dist --include-files config.ini
}

start() {
  echo "Starting game ..."
  dist/run_seekers examples/ai-decide.py examples/ai-simple.py
}

[ $# -eq 0 ] && usage
while getopts ":bs" arg; do
    case $arg in
        b)
            build
            ;;
        s)
            start
            ;;
        *)
            usage
            ;;
    esac
done
