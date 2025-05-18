# Parse command line arguments
while [[ $# -gt 0 ]]; do
	case $1 in
		--prefix)
			NAT64_PREFIX="$2"
			shift 2
			;;
		--via)
			NAT64_IPV6="$2"
			shift 2
			;;
		--dev)
			NAT64_INTERFACE="$2"
			shift 2
			;;
		*)
			echo "Unknown argument: $1"
			exit 1
			;;
	esac
done

if [ -z "${NAT64_PREFIX}" ]; then
  NAT64_PREFIX="64:ff9b::/96"
fi

if [ -z "${NAT64_INTERFACE}" ]; then
  if [ -n "${NAT64_IPV6}" ]; then
    dev=$(ip -6 route get ${NAT64_IPV6} | sed 's/.*dev \([^ ]*\).*/\1/')
    if [ -n "${dev}" ]; then
      NAT64_INTERFACE="${dev}"
    fi
  fi
fi

if [ -z "${NAT64_INTERFACE}" ]; then
  echo "--dev is required"
  exit 1
fi

while true; do
  if [ -z "${NAT64_IPV6}" ]; then
	  output=$(ip route add ${NAT64_PREFIX} dev ${NAT64_INTERFACE} 2>&1)
  else
    output=$(ip route add ${NAT64_PREFIX} via ${NAT64_IPV6} dev ${NAT64_INTERFACE} 2>&1)
  fi
	case "$output" in
		*"Host is unreachable"*)
			printf "Startup error: Nat64 host not ready yet...\n"
			sleep 1
			;;
		*)
			break
			;;
	esac
done
