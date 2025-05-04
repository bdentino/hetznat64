Testing:

- Test simple server & agent connectivity on pi & hetzner (might need to investigate persistent keepalive for wireguard)

Nat64:

- Setup cloudflare dns64
- Run nat64 service in server container
- Disable ipv4 on agents in docker-compose.yml
- Figure out how to route ipv4 traffic from agent containers to nat64 in server container

Reliability:

- Handle scale in, scale out, restart of agents
- Handle restart of server [DONE]
- Handle change of server ip address
- Tests & healthchecks based on connectivity

Improvements:

- Investigate panic with altuntun, see if we can switch back and check if performance is better
- Move wg setup from entrypoint to a separate script and replace individual sudoers commands [DONE]
- Support for kernelspace wireguard [DONE]
- Preshared key support
- Key rotation

Deployment:

- Setup dns64 on hetzner hosts via terraform
- Figure out how to get all containers on host to use nat64 agent for 6to4 traffic
- Add agent to cloud-init userdata in hetzner terraform
