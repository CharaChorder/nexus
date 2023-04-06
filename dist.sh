#!/usr/bin/env bash

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

pip install -r src/requirements.txt

if [ "$(uname -s)" == "Darwin" ]; then
    pyinstaller src/darwin.spec
else
    pyinstaller src/xorg.spec
fi
