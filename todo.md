Testing:

- Test simple server & agent connectivity on pi & hetzner (might need to investigate persistent keepalive for wireguard) [DONE]

Nat64:

- Setup cloudflare dns64 [DONE]

- Run nat64 service in container [DONE]

  - start tayga container
    - mkdir -p /dev/net
    - mknod /dev/net/tun c 10 200
    - /docker-entry.sh
  - get local ipv6 of container (or specify in docker command)
  - create route on host to route dns64 prefix via container ip
    - sudo ip route add $TAYGA_CONF_PREFIX via <container ipv6> dev eth0
      - (figure out how to make route persist across reboots)
  - This should work for 6to4 traffic from host (outside docker) or from any container with ipv6 connectivity

- add ipv6 support to default bridge network on hetzner so all containers get ipv6 by default (ipv6: true, fixed-cidr-v6: fd00:feed:baba::/48) https://docs.docker.com/engine/daemon/ipv6/
- "default-network-opts": {
  "bridge": {
  "com.docker.network.enable_ipv6": "true"
  }
  }

- Disable ipv4 on agents in docker-compose.yml (possible?)

  - Not possible because dns doesn't work over ipv6 (see https://github.com/docker/for-mac/issues/7676)

- Figure out how to route ipv4 traffic from agent containers to nat64 in server container [DONE]
  - Run wireguard server & agent on different hosts
  - Run nat64 on server host
  - figure out how to route nat64 prefix from agent host through wireguard to nat64 service
  - Need to add route in agent so nat64 traffic goes through wg
    - `ip -6 route add $TAYGA_CONF_PREFIX dev <wireguard interface>`
  - Need to add route in tayga so wg client ips go back through wg interface
    - `ip -6 route add $WG_SUBNET via $WG_SERVER_NAT64_IP dev <nat64 interface>`

Reliability:

- Handle scale in, scale out, restart of agents
- Handle restart of server [DONE]
- Handle change of server ip address
- Healthchecks based on connectivity [DONE]
- Tests

Improvements:

- Investigate panic with altuntun, see if we can switch back and check if performance is better
- Move wg setup from entrypoint to a separate script and replace individual sudoers commands [DONE]
- Support for kernelspace wireguard [DONE]
- Preshared key support
- Key rotation
- HTTPS trusted CA & client cert validation for agent/server communication

Deployment:

- Setup dns64 on hetzner hosts via terraform
- Figure out how to get all containers on host to use nat64 agent for 6to4 traffic
- Add agent to cloud-init userdata in hetzner terraform
