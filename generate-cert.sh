#!/bin/sh

# Parse command line arguments
ca_file=""
out_dir=""
days=900

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ca=*)
            ca_file="${1#*=}"
            shift
            ;;
        --dev=*)
            # Store devices in colon-separated string since arrays not available in sh
            if [ -z "$devices" ]; then
                devices="${1#*=}"
            else
                devices="$devices:${1#*=}"
            fi
            shift
            ;;
        --host=*)
            # Store hostnames in colon-separated string
            if [ -z "$hostnames" ]; then
                hostnames="${1#*=}"
            else
                hostnames="$hostnames:${1#*=}"
            fi
            shift
            ;;
        --out=*)
            out_dir="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Validate CA file is specified and exists
if [ -z "$ca_file" ]; then
    echo "Error: --ca argument is required"
    exit 1
fi

if [ ! -f "$ca_file" ]; then
    echo "Error: CA file $ca_file does not exist"
    exit 1
fi

# Create temp directory for intermediate files
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

# Generate private key
openssl genrsa -out "$tmp_dir/cert.key" 4096

# Build SAN extension string
san="subjectAltName=DNS:localhost"

# Add additional hostnames if specified
if [ -n "$hostnames" ]; then
    OLDIFS="$IFS"
    IFS=:
    for host in $hostnames; do
        san="$san,DNS:$host"
    done
    IFS="$OLDIFS"
fi

first=false

# Add IPs from specified interfaces
# Split colon-separated devices string
# Save original IFS and set new one for device splitting
OLDIFS="$IFS"
IFS=:
for dev in $devices; do
    # Restore original IFS for commands that need default word splitting
    IFS="$OLDIFS"

    # Wait up to 10 seconds for interface to be available
    count=0
    while [ ! -e "/sys/class/net/$dev" ] && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if [ ! -e "/sys/class/net/$dev" ]; then
        echo "Warning: Interface $dev not found after 10 seconds"
        continue
    fi

    # Get IPv4 addresses - explicitly set field separator for awk
    ipv4s=$(ip -4 addr show dev "$dev" 2>/dev/null | grep inet | awk -F' ' '{print $2}' | cut -d/ -f1)
    for ip in $ipv4s; do
        if [ "$first" = true ]; then
            first=false
        else
            san="$san,"
        fi
        san="${san}IP:$ip"
    done

    # Get IPv6 addresses - explicitly set field separator for awk
    ipv6s=$(ip -6 addr show dev "$dev" 2>/dev/null | grep inet6 | awk -F' ' '{print $2}' | cut -d/ -f1)
    for ip in $ipv6s; do
        if [ "$first" = true ]; then
            first=false
        else
            san="$san,"
        fi
        san="${san}IP:$ip"
    done

    # Reset IFS for next device iteration
    IFS=:
done
# Restore original IFS
IFS="$OLDIFS"

# Generate CSR with dummy values
openssl req -new -key "$tmp_dir/cert.key" -out "$tmp_dir/cert.csr" \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=localhost"

# Create extension file
echo "basicConstraints=CA:FALSE" > "$tmp_dir/ext.conf"
echo "keyUsage=digitalSignature,keyEncipherment" >> "$tmp_dir/ext.conf"
echo "extendedKeyUsage=serverAuth,clientAuth" >> "$tmp_dir/ext.conf"
echo "$san" >> "$tmp_dir/ext.conf"

cat "$tmp_dir/ext.conf"

# Sign the CSR with the CA
openssl x509 -req -days $days \
    -in "$tmp_dir/cert.csr" \
    -CA "$ca_file" \
    -CAkey "${ca_file%.*}.key" \
    -out "$tmp_dir/cert.pem" \
    -extfile "$tmp_dir/ext.conf"

if [ -n "$out_dir" ]; then
    # Create output directory if it doesn't exist
    mkdir -p "$out_dir"

    # Bundle CA certificate with the server certificate
    cat "$ca_file" >> "$tmp_dir/cert.pem"

    # Copy files to output directory
    cp "$tmp_dir/cert.key" "$out_dir/cert.key"
    cp "$tmp_dir/cert.pem" "$out_dir/cert.pem"
    chmod 644 "$out_dir/cert.pem"
    chmod 600 "$out_dir/cert.key"
else
    # Print to stdout
    echo "=== Private Key ==="
    cat "$tmp_dir/cert.key"
    echo
    echo "=== Certificate ==="
    cat "$tmp_dir/cert.pem"
fi
