#!/bin/bash

ln -sf settings-docker.py settings.py

exec gosu maymunai "$@"