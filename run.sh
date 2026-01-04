#!/usr/bin/with-contenv bashio

# Export the Home Assistant addon options path
export CONFIG_PATH="/data/options.json"

python3 ./server.py