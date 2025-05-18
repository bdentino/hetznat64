TAYGA_CONF_DIR=${TAYGA_CONF_DIR:-/usr/local/etc/tayga}
TAYGA_CONF_DATA_DIR=${TAYGA_CONF_DATA_DIR:-/var/db/tayga}

default_ip4=$(ip -4 addr show eth0 | grep inet | awk '{ print $2 }' | cut -d'/' -f1)
default_ip6=$(ip -6 addr show eth0 | grep inet6 | grep global | head -n1 | awk '{ print $2 }' | cut -d'/' -f1)

# Create Tayga config if it doesn't exist
if [ ! -f ${TAYGA_CONF_DIR}/tayga.conf ]; then
  echo "Creating Tayga config"
	mkdir -p ${TAYGA_CONF_DATA_DIR} ${TAYGA_CONF_DIR}

	TAYGA_CONF_IPV4_ADDR=${TAYGA_CONF_IPV4_ADDR:-${default_ip4}}

	# create a cidr with the last 32 addresses of the subnet for eth0
	TAYGA_CONF_DYNAMIC_POOL=${TAYGA_CONF_DYNAMIC_POOL:-${default_ip4%.*}.128/25}

	TAYGA_CONF_PREFIX=${TAYGA_CONF_PREFIX:-fd00:6464:64:ff9b::/96}

	cat >${TAYGA_CONF_DIR}/tayga.conf <<-EOF
	tun-device nat64
	data-dir ${TAYGA_CONF_DATA_DIR}
	ipv4-addr ${TAYGA_CONF_IPV4_ADDR}
	dynamic-pool ${TAYGA_CONF_DYNAMIC_POOL}
	prefix ${TAYGA_CONF_PREFIX}
	EOF
fi

# Make network tunnel if it doesn't exist
if [ ! -c /dev/net/tun ]; then
	mkdir -p /dev/net
	mknod /dev/net/tun c 10 200
  chown tayga:tayga /dev/net/tun
fi


# Setup Tayga networking
dynamicpool=$(cat ${TAYGA_CONF_DIR}/tayga.conf | grep "dynamic-pool" | cut -d' ' -f2)
prefix=$(cat ${TAYGA_CONF_DIR}/tayga.conf | grep "prefix" | cut -d' ' -f2)
tayga -c ${TAYGA_CONF_DIR}/tayga.conf --mktun
ip link set nat64 up
ip link set nat64 mtu 1460

# add default addresses to nat64 interface (to ensure proper icmp functionality)
ip -4 addr add ${default_ip4} dev nat64
ip -6 addr add ${default_ip6} dev nat64

# setup tayga subnets to route through nat64
ip -6 route add ${prefix} dev nat64
ip -4 route add ${dynamicpool} dev nat64

# If WG_NAT64_IP (NAT64 gateway) and WG_NETWORK (Wireguard network) env vars are set
if [ -n "${WG_NAT64_IP}" -a -n "${WG_NETWORK}" ]; then
	echo "Setting up tayga to route Wireguard network traffic through NAT64 gateway"
  # Get the network interface that can reach the NAT64 gateway
  dev=$(ip -6 route get ${WG_NAT64_IP} | sed 's/.*dev \([^ ]*\).*/\1/')
  # If we found a valid interface
  if [ -n "${dev}" ]; then
		echo "Found interface ${dev} that can reach NAT64 gateway ${WG_NAT64_IP}"
    # Add IPv6 route to send Wireguard network traffic through the NAT64 gateway
    ip -6 route add ${WG_NETWORK} via ${WG_NAT64_IP} dev ${dev}
  fi
fi

# setup postrouting rules for tayga ipv4 traffic
iptables -t nat -A POSTROUTING -s ${dynamicpool} -j MASQUERADE

echo "Starting Tayga"

exec tayga -u tayga -g tayga -c ${TAYGA_CONF_DIR}/tayga.conf -d
