#!/usr/bin/with-contenv bashio

# Home Assistant addon options are stored in /data/options.json
# Export the path so server.py can find it
export CONFIG_PATH="/data/options.json"

python3 ./server.py