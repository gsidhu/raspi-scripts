#!/bin/bash

set -x # enable debug output

# Make sure to chmod +x start-server.sh

# This script sets up the necessary environment for services
# that need to talk to PulseAudio or other D-Bus session services.

# Wait for the user's D-Bus session to be available
while [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; do
    # Source the dbus session environment from the systemd user session
    if [ -r "${XDG_RUNTIME_DIR}/bus" ]; then
        export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
    fi
    sleep 1
done

# Now, execute the actual uvicorn server
# The full path to the python interpreter in the venv is used for robustness
/home/thatgurjot/radio-server/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 >> pi-radio-server.log 2>&1