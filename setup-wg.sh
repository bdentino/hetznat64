# Parse command line arguments
while [[ $# -gt 0 ]]; do
	case $1 in
		--ip4)
			WG_IPV4="$2"
			shift 2
			;;
		--ip6)
			WG_IPV6="$2"
			shift 2
			;;
		--port)
			WG_PORT="$2"
			shift 2
			;;
		--name)
			WG_INTERFACE="$2"
			shift 2
			;;
		*)
			echo "Unknown argument: $1"
			exit 1
			;;
	esac
done

# Set defaults if not provided
if [ -z "${WG_IPV4}" ]; then
	echo "--ip4 is required"
	exit 1
fi

if [ -z "${WG_IPV6}" ]; then
	echo "--ip6 is required"
	exit 1
fi

if [ -z "${WG_INTERFACE}" ]; then
	echo "--name is required"
	exit 1
fi

if [ -z "${WG_PORT}" ]; then
	echo "--port is required"
	exit 1
fi

mkdir -p /config
touch /config/wireguard.conf
chown wireguard:wireguard /config/wireguard.conf

# Setup boringtun interface and start
if [ -f /usr/local/bin/boringtun ]; then
	printf "Starting Wireguard userspace (boringtun)\n";
	mkdir -p /dev/net;
	mknod /dev/net/tun c 10 200;
	chown wireguard:wireguard /dev/net/tun;
	/usr/local/bin/boringtun -f ${WG_INTERFACE} --disable-multi-queue &
	wireguard_pid=$!;
else
	printf "WARNING: Wireguard binary not found. This container will not run\n";
	exit 1;
fi

# Add a sleep for any Wireguard intialization slowness
while true; do
	output=$(wg show ${WG_INTERFACE} 2>&1)
	case "$output" in
		*"Protocol not supported"*|*"No such device"*)
			printf "Startup error: protocol not supported: sleeping...\n"
			sleep 1
			;;
		*)
      chown wireguard:wireguard -R /var/run/wireguard
			break
			;;
	esac
done

# Extract containers default gateway interface (usually eth0)
read _ _ _ _ iface < <(ip route show default);

# This sets the IPv4 VPN network on the server side. Can be changed by env var.
ip4out=$(ip addr add $WG_IPV4 dev ${WG_INTERFACE})
# printf "Setting ipv4 network address options... $ip4out\n";
# sysctl -w net.ipv6.conf.${WG_INTERFACE}.disable_ipv6=0
ip6out=$(ip addr add $WG_IPV6 dev ${WG_INTERFACE})
# printf "Setting ipv6 network address options... $ip6out\n";

# First delete the rule (this avoids adding the rule every time the container restarts - also errors out gracefully)

# printf "Deleting rules (if they exist)...\n"
iptables-legacy -D FORWARD -i ${WG_INTERFACE} -j ACCEPT \
  && iptables-legacy -D FORWARD -i $iface -j ACCEPT \
  && iptables-legacy -t nat -D POSTROUTING -o $iface -j MASQUERADE;
# printf "Configuring iptables-legacy $iface...\n"
iptables-legacy -A FORWARD -i ${WG_INTERFACE} -j ACCEPT \
  && iptables-legacy -A FORWARD -i $iface -j ACCEPT \
  && iptables-legacy -t nat -A POSTROUTING -o $iface -j MASQUERADE;

if [ -f /config/iptables.sh ]; then
	source /config/iptables.sh;
fi

# Set MTU lower than the default 1500 accounting for wg overhead
mtuout=$(ip link set mtu 1420 qlen 1000 dev ${WG_INTERFACE})
# printf "Setting network interface mtu... $mtuout\n";

# Set wireguard configuration
if [ -f /config/wireguard.conf ]; then
		wgout=$(wg setconf ${WG_INTERFACE} /config/wireguard.conf)
		printf "Setting config... $wgout\n";
else
		printf "WARNING: /config/wireguard.conf file is missing. This container cannot start\n";
		exit 1;
fi

# This brings up the wireguard interface inside the container
ipup=$(ip link set ${WG_INTERFACE} up)
printf "Bringing interface up... $ipup\n";

# Display the running configs
# printf "${nl}Active network interfaces:\n$(ip addr 2>&1)";
# printf "${nl}Active network ipv4 route table:\n$(ip -4 route)";
# printf "${nl}iptables-legacy ipv4 config:\n$(iptables-legacy -t nat -L)";
# printf "${nl}Active Wireguard config:\n$(wg show ${WG_INTERFACE} 2>&1)";

# Test ping to Google for connectivity validation
# printf "${nl}IPv4 connectivity validation:\n" && /bin/ping -4 -q -c 1 ipv4.google.com;
printf "${nl}Running....\n"

wait $wireguard_pid
