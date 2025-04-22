#! /bin/sh

nl="\n-------------------------------------\n";

# Function to handle termination signals
cleanup() {
    printf "${nl}Received termination signal, cleaning up...${nl}";
    # Kill the wireguard process if it's still running
    if [ -n "$wireguard_pid" ]; then
        kill $wireguard_pid 2>/dev/null || true;
    fi

    # Kill the child process if it's still running
    if [ -n "$child_pid" ]; then
        kill $child_pid 2>/dev/null || true;
    fi
}

# Register signal handlers
trap cleanup SIGINT SIGTERM;

# Check IP subnet for container:
if [ -z "${WG_IPV4}" ]; then
	export WG_IPV4=10.0.0.0/24;
fi

if [ -z "${WG_IPV6}" ]; then
	export WG_IPV6=fd00:6464::1/64;
fi

if [ -z "${WG_INTERFACE}" ]; then
	export WG_INTERFACE=wg0;
fi

if [ -z "${WG_PORT}" ]; then
	export WG_PORT=51820;
fi

sudo mkdir -p /config
sudo touch /config/wireguard.conf
sudo chown wireguard:wireguard /config/wireguard.conf

# Setup altuntun interface and start
if [ -f /usr/local/bin/altuntun ]; then
	printf "Starting Wireguard userspace (altuntun)\n";
	sudo mkdir -p /dev/net;
	sudo mknod /dev/net/tun c 10 200;
	sudo chown wireguard:wireguard /dev/net/tun;
	sudo /usr/local/bin/altuntun -f ${WG_INTERFACE} --disable-multi-queue &
	wireguard_pid=$!;
else
	printf "WARNING: Wireguard binary not found. This container will not run\n";
	exit 1;
fi

# Add a sleep for any Wireguard intialization slowness
while true; do
	output=$(sudo wg show ${WG_INTERFACE} 2>&1)
	case "$output" in
		*"Protocol not supported"*|*"No such device"*)
			printf "Startup error: protocol not supported: sleeping...\n"
			sleep 1
			;;
		*)
      sudo chown wireguard:wireguard -R /var/run/wireguard
			break
			;;
	esac
done

# Extract containers default gateway interface (usually eth0)
read _ _ _ _ iface < <(sudo ip route show default);

# This sets the IPv4 VPN network on the server side. Can be changed by env var.
ip4out=$(sudo ip addr add $WG_IPV4 dev ${WG_INTERFACE})
# printf "Setting ipv4 network address options... $ip4out\n";
ip6out=$(sudo ip addr add $WG_IPV6 dev ${WG_INTERFACE})
# printf "Setting ipv6 network address options... $ip6out\n";

# First delete the rule (this avoids adding the rule every time the container restarts - also errors out gracefully)

# printf "Deleting rules (if they exist)...\n"
sudo iptables-legacy -D FORWARD -i ${WG_INTERFACE} -j ACCEPT \
  && sudo iptables-legacy -D FORWARD -i $iface -j ACCEPT \
  && sudo iptables-legacy -t nat -D POSTROUTING -o $iface -j MASQUERADE;
# printf "Configuring iptables-legacy $iface...\n"
sudo iptables-legacy -A FORWARD -i ${WG_INTERFACE} -j ACCEPT \
  && sudo iptables-legacy -A FORWARD -i $iface -j ACCEPT \
  && sudo iptables-legacy -t nat -A POSTROUTING -o $iface -j MASQUERADE;

if [ -f /config/iptables.sh ]; then
	source /config/iptables.sh;
fi

# Set MTU lower than the default 1500 accounting for wg overhead
mtuout=$(sudo ip link set mtu 1420 qlen 1000 dev ${WG_INTERFACE})
# printf "Setting network interface mtu... $mtuout\n";

# Set wireguard configuration
if [ -f /config/wireguard.conf ]; then
		wgout=$(sudo wg setconf ${WG_INTERFACE} /config/wireguard.conf)
		printf "Setting config... $wgout\n";
else
		printf "WARNING: /config/wireguard.conf file is missing. This container cannot start\n";
		exit 1;
fi

# This brings up the wireguard interface inside the container
ipup=$(sudo ip link set ${WG_INTERFACE} up)
printf "Bringing interface up... $ipup\n";

# Display the running configs
# printf "${nl}Active network interfaces:\n$(sudo ip addr 2>&1)";
# printf "${nl}Active network ipv4 route table:\n$(sudo ip -4 route)";
# printf "${nl}iptables-legacy ipv4 config:\n$(sudo iptables-legacy -t nat -L)";
# printf "${nl}Active Wireguard config:\n$(sudo wg show ${WG_INTERFACE} 2>&1)";

# Test ping to Google for connectivity validation
# printf "${nl}IPv4 connectivity validation:\n" && /bin/ping -4 -q -c 1 ipv4.google.com;
printf "${nl}Running....\n"

"$@" &
child_pid=$!

wait -n;
printf "${nl}WARNING: Process terminated, cleaning up...${nl}";
cleanup;
