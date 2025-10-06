#!/usr/bin/env bash

# Script to extract and export configuration variables from JSON files
# Can be sourced by other scripts to avoid duplication

set -o nounset
set -o errexit

# Determine the base directory for config files
if [ -n "${1:-}" ]
then
    CONFIG_BASE_DIR="$1"
else
    # Default paths based on where this script might be called from
    if [ -f "test_config/websocket_server/config.json" ]
    then
        CONFIG_BASE_DIR="test_config"
    elif [ -f "/app/test_config/websocket_server/config.json" ]
    then
        CONFIG_BASE_DIR="/app/test_config"
    else
        echo "ERROR: Cannot find config files. Please specify CONFIG_BASE_DIR as first argument"
        exit -1
    fi
fi

# Verify config files exist
SERVER_CONFIG="$CONFIG_BASE_DIR/websocket_server/config.json"
CLIENT1_CONFIG="$CONFIG_BASE_DIR/websocket_client_1/config.json"
CLIENT2_CONFIG="$CONFIG_BASE_DIR/websocket_client_2/config.json"

if [ ! -f "$SERVER_CONFIG" ]
then
    echo "ERROR: Server config not found at $SERVER_CONFIG"
    exit -1
fi

if [ ! -f "$CLIENT1_CONFIG" ]
then
    echo "ERROR: Client1 config not found at $CLIENT1_CONFIG"
    exit -1
fi

if [ ! -f "$CLIENT2_CONFIG" ]
then
    echo "ERROR: Client2 config not found at $CLIENT2_CONFIG"
    exit -1
fi

echo "Extracting ports from configuration files..."

# Server configuration
export SERVER_WS_PORT=$(jq -r '.dataExchange.serverUrl | match(":([0-9]+)") | .captures[0].string' "$SERVER_CONFIG")
export SERVER_LISTEN_PORTS=$(jq -r '.tcpTunnelListens[].listenPort' "$SERVER_CONFIG" | tr '\n' ' ')

# Client 1 configuration  
export CLIENT1_LISTEN_PORTS=$(jq -r '.tcpTunnelListens[].listenPort' "$CLIENT1_CONFIG" | tr '\n' ' ')

# Client 2 configuration
export CLIENT2_LISTEN_PORTS=$(jq -r '.tcpTunnelListens[].listenPort' "$CLIENT2_CONFIG" | tr '\n' ' ')

# All connect-to ports that tests need to listen on
export ALL_CONNECT_PORTS=$(jq -r '.tcpTunnelConnects[].connectToPort' "$SERVER_CONFIG" "$CLIENT1_CONFIG" "$CLIENT2_CONFIG" | sort -u | tr '\n' ' ')

echo "Exported configuration variables:"
echo "  SERVER_WS_PORT=$SERVER_WS_PORT"
echo "  SERVER_LISTEN_PORTS=$SERVER_LISTEN_PORTS"
echo "  CLIENT1_LISTEN_PORTS=$CLIENT1_LISTEN_PORTS"
echo "  CLIENT2_LISTEN_PORTS=$CLIENT2_LISTEN_PORTS"
echo "  ALL_CONNECT_PORTS=$ALL_CONNECT_PORTS"