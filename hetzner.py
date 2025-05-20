import os
import hashlib

from typing import List, Dict, Any, Set
from fastapi import FastAPI, Query
from pydantic import BaseModel
import docker
import uvicorn

app = FastAPI()
client = docker.from_env()

# Get the discovery label prefix from environment variable, default to "hetznat64"
DISCOVERY_LABEL_PREFIX = os.getenv("DISCOVERY_LABEL_PREFIX", "hetznat64")

def container_name_to_int(name: str) -> int:
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) % (2**31)

def get_container_networks(container) -> Set[str]:
    """Get the set of network names that a container is connected to."""
    try:
        networks = container.attrs['NetworkSettings']['Networks']
        return {net_name for net_name in networks.keys()}
    except Exception:
        return set()

def get_current_container() -> docker.models.containers.Container:
    """Get the current container object."""
    # Get the container ID from the hostname (Docker sets hostname to container ID)
    container_id = os.environ.get('HOSTNAME')
    if not container_id:
        raise RuntimeError("Could not determine current container ID")
    return client.containers.get(container_id)

def get_container_ipv4(container) -> str:
    """Get the IPv4 address of a container, or return localhost if none found."""
    try:
        # Get the network settings for the container
        network_settings = container.attrs['NetworkSettings']

        # Try to get IPv4 address from networks
        for network in network_settings.get('Networks', {}).values():
            if 'IPAddress' in network and network['IPAddress']:
                return network['IPAddress']

        # If no IPv4 address found, return localhost
        return "127.0.0.1"
    except Exception:
        return "127.0.0.1"

def get_container_ipv6(container) -> str:
    """Get the IPv6 address of a container, or return localhost if none found."""
    try:
        # Get the network settings for the container
        network_settings = container.attrs['NetworkSettings']

        # Try to get IPv6 address from networks
        for network in network_settings.get('Networks', {}).values():
            if 'GlobalIPv6Address' in network and network['GlobalIPv6Address']:
                return network['GlobalIPv6Address']

        # If no IPv6 address found, return localhost
        return "::1"
    except Exception:
        return "::1"

def get_mock_servers(label_selector: str = None) -> List[Dict[str, Any]]:
    """Get a list of mock servers based on running Docker containers."""
    servers = []

    # Get the current container and its networks
    current_container = get_current_container()
    current_networks = get_container_networks(current_container)

    # Get all containers
    containers = client.containers.list()

    for container in containers:
        # Skip the current container
        if container.id == current_container.id:
            continue

        # Get container's networks
        container_networks = get_container_networks(container)

        # Check if container shares any network with current container
        if not current_networks.intersection(container_networks):
            continue

        # Check if container has the required label
        labels = container.labels or {}
        if f"{DISCOVERY_LABEL_PREFIX}.status" in labels and labels[f"{DISCOVERY_LABEL_PREFIX}.status"] == "waiting":
            # If label_selector is provided, check if container matches it
            if label_selector:
                # Parse the label selector (simple implementation for now)
                # Format expected: "key=value" or "key"
                parts = label_selector.split("=")
                key = parts[0]
                if len(parts) > 1:
                    value = parts[1]
                    if key not in labels or labels[key] != value:
                        continue
                else:
                    if key not in labels:
                        continue

            # Get container's IPv6 address
            ipv6 = get_container_ipv6(container)
            ipv4 = get_container_ipv4(container)

            # Create mock server object
            server = {
                "id": container_name_to_int(container.name),
                "name": container.id,
                "status": "running",
                "public_net": {
                    "ipv4": {
                        "id": 1,
                        "ip": ipv4,
                        "blocked": False,
                        "dns_ptr": []
                    },
                    "ipv6": {
                        "id": 2,
                        "ip": f"{ipv6}/64",
                        "blocked": False,
                        "dns_ptr": []
                    },
                    "floating_ips": []
                },
                # Add other required fields with mock values
                "server_type": {
                    "id": 1,
                    "name": "cx11",
                    "description": "CX11",
                    "cores": 1,
                    "memory": 2.0,
                    "disk": 20,
                    "prices": []
                },
                "datacenter": {
                    "id": 1,
                    "name": "nbg1-dc3",
                    "description": "Nuremberg 1 DC 3",
                    "location": {
                        "id": 1,
                        "name": "nbg1",
                        "description": "Nuremberg DC Park 1",
                        "country": "DE",
                        "city": "Nuremberg",
                        "latitude": 49.452102,
                        "longitude": 11.076665
                    }
                },
                "image": {
                    "id": 1,
                    "type": "system",
                    "status": "available",
                    "name": "ubuntu-20.04",
                    "description": "Ubuntu 20.04 LTS",
                    "image_size": 2.3,
                    "disk_size": 10,
                    "created": "2020-05-01T12:00:00+00:00",
                    "created_from": None,
                    "bound_to": None,
                    "os_flavor": "ubuntu",
                    "os_version": "20.04",
                    "rapid_deploy": False
                },
                "iso": None,
                "rescue_enabled": False,
                "locked": False,
                "created": "2020-05-01T12:00:00+00:00",
                "included_traffic": 2199023255552,
                "outgoing_traffic": 123456,
                "ingoing_traffic": 123456,
                "backup_window": "22-02",
                "protection": {
                    "delete": False,
                    "rebuild": False
                },
                "labels": labels,
                "volumes": [],
                "load_balancers": [],
                "primary_disk_size": 20,
                "placement_group": None
            }
            servers.append(server)

    return servers

class ServersResponse(BaseModel):
    servers: List[Dict[str, Any]]
    meta: Dict[str, Any]

@app.get("/v1/servers", response_model=ServersResponse)
async def get_servers(label_selector: str = Query(None)):
    """Mock endpoint for GET /v1/servers."""
    servers = get_mock_servers(label_selector)

    response = {
        "servers": servers,
        "meta": {
            "pagination": {
                "page": 1,
                "per_page": len(servers),
                "previous_page": None,
                "next_page": None,
                "last_page": 1,
                "total_entries": len(servers)
            }
        }
    }

    return response

if __name__ == '__main__':
    uvicorn.run(app, host=["::", "0.0.0.0"], port=5000)
