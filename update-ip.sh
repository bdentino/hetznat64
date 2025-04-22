#!/bin/sh

# Validate the first argument as a valid IPv6 CIDR
regex='^([0-9a-fA-F]{0,4}:){1,7}[0-9a-fA-F]{0,4}/[0-9]{1,3}$'
var="$1"

if [[ ! $var =~ $regex ]]; then
    echo "Invalid IPv6 CIDR range: $var"
    exit 1
fi

# Get the interface name from the environment variable
WG_INTERFACE=${WG_INTERFACE:-"hetznat64"}

# Delete existing IPv6 addresses on the interface
ip -6 addr flush dev $WG_INTERFACE

# Add the new IPv6 address
ip -6 addr add $1 dev $WG_INTERFACE
