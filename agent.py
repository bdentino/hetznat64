import os
import ssl
import socket
import subprocess
import threading
import time
from ipaddress import ip_interface, IPv6Interface
from dataclasses import dataclass

import hcloud
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from wireguard_tools import WireguardConfig, WireguardDevice, WireguardKey, WireguardPeer

@dataclass(kw_only=True)
class Hetznat64AgentConfig:
    # Wireguard config
    wg_interface: str
    wg_port: int

    # Control server details
    control_server_hostname: str

    # Agent server config
    rest_port: int = 5001
    cert_file: str = None
    key_file: str = None
    ca_file: str = None

    # Hetzner Cloud API
    api_key: str
    api_endpoint: str = "https://api.hetzner.cloud/v1"
    discovery_label_prefix: str = "hetznat64"

class Hetznat64Agent:
    def __init__(self, config: Hetznat64AgentConfig):
        self.__lock = threading.Lock()
        self.__state_label = f'{config.discovery_label_prefix}.status'
        self.__state = 'initializing'
        self.__control_ip = None
        self.__config = config
        self.__wg_key = None
        self.__client = hcloud.Client(token=self.__config.api_key, api_endpoint=self.__config.api_endpoint)
        self.__app = FastAPI()
        self.__setup_routes()

    def __get_state(self):
        with self.__lock:
            return self.__state

    def __set_state(self, value):
        with self.__lock:
            if self.__state != value:
                print(f"Updating state from {self.__state} to {value}")
                self.__state = value
                self.add_labels({ self.__state_label: value })

    def __get_control_ip(self):
        with self.__lock:
            return self.__control_ip

    def __set_control_ip(self, value):
        with self.__lock:
            self.__control_ip = value

    def __check_connection(self):
        recheck = 0
        while True:
            recheck += 1
            control_ip = self.__get_control_ip()
            state = self.__get_state()
            if control_ip and (state != 'connected' or recheck >= 20):
                ping_ip = str(IPv6Interface(control_ip).ip)
                try:
                    ping_result = subprocess.run(
                        ["ping6", "-c", "1", "-W", "2", ping_ip],
                        capture_output=True
                    )
                    recheck = 0
                    if ping_result.returncode == 0:
                        print(f"Ping to {ping_ip} succeeded")
                        self.__set_state('connected')
                    else:
                        print(f"Ping to {ping_ip} failed")
                        self.__set_state('waiting')
                except Exception as e:
                    print(f"Ping process failed for {ping_ip}: {e}")
            elif not control_ip and state != 'waiting':
                self.__set_state('waiting')
            time.sleep(1)

    def add_labels(self, labels: dict):
        server_id = os.environ.get('HOSTNAME', None)
        try:
            if os.path.exists("/var/lib/cloud/data/instance-id"):
                with open("/var/lib/cloud/data/instance-id", "r") as f:
                    server_id = f.read().strip()
        except Exception:
            pass

        server = self.__client.servers.get_by_id(server_id)
        existing_labels = server.labels or {}
        existing_labels.update(labels)
        server.update(labels=existing_labels)

    def start(self):
        self.__set_control_ip(None)
        threading.Thread(target=self.__check_connection, daemon=True).start()
        uvicorn.run(self.__app, host='::', port=self.__config.rest_port,
                    ssl_certfile=self.__config.cert_file,
                    ssl_keyfile=self.__config.key_file,
                    ssl_ca_certs=self.__config.ca_file,
                    ssl_cert_reqs=ssl.CERT_REQUIRED
        )

    def __setup_routes(self):
        self.__app.get('/ready')(self.__ready)
        self.__app.get('/health')(self.__health)
        self.__app.post('/handshake')(self.__handshake)

    async def __ready(self):
        return {"status": "ok"}

    async def __health(self):
        if self.__get_state() != 'connected':
            raise HTTPException(status_code=500, detail="Not connected to control server")
        return {"status": "ok"}

    async def __handshake(self, request: Request):
        data = await request.json()
        agent_ip = data.get('agent_ip')
        control_ip = data.get('control_ip')
        control_port = data.get('control_port')
        public_key = data.get('public_key')
        preshared_key = data.get('preshared_key', None)

        self.__control_ip = control_ip
        if not self.__wg_key:
            self.__wg_key = WireguardKey.generate()

        # Extract prefix from control_ip and apply to agent_ip
        control_prefix = str(ip_interface(control_ip).network)
        agent_ip_addr = ip_interface(agent_ip).ip
        new_agent_ip = f"{agent_ip_addr}/{control_prefix.split('/')[-1]}"

        # Check and update Wireguard configuration
        config = WireguardConfig(
            addresses=[IPv6Interface(agent_ip)],
            private_key=self.__wg_key,
            listen_port=self.__config.wg_port,
        )

        # Resolve the control server hostname to get its IPv6 address
        try:
            addrinfo = socket.getaddrinfo(self.__config.control_server_hostname, None, socket.AF_INET6)
            endpoint_host = addrinfo[0][4][0]  # Get the first IPv6 address
        except socket.gaierror as e:
            print(f"Failed to resolve IPv6 address for {self.__config.control_server_hostname}: {e}")
            endpoint_host = self.__config.control_server_hostname
        config.add_peer(WireguardPeer(
            friendly_name="control",
            public_key=public_key,
            preshared_key=preshared_key,
            endpoint_host=endpoint_host,
            endpoint_port=control_port,
            allowed_ips=[control_ip, IPv6Interface("64:ff9b::/96")],
        ))

        current_config = WireguardDevice.get(self.__config.wg_interface).get_config()
        current_peer = next(iter(current_config.peers.keys()), None)
        new_peer = next(iter(config.peers.keys()), None)
        if current_peer != new_peer:
            print(f"Updating Wireguard configuration")
            print('current_peer', current_peer)
            print('new_peer', new_peer)
            subprocess.run(["/usr/bin/sudo", "/update-ip.sh", str(ip_interface(new_agent_ip))], check=True)
            WireguardDevice.get(self.__config.wg_interface).set_config(config)

        response = {
            'public_key': str(self.__wg_key.public_key()),
            'port': self.__config.wg_port,
        }
        return response

if __name__ == "__main__":
    interface = os.environ.get("WG_INTERFACE", "hetznat64")
    port = os.environ.get("WG_PORT", "51820")
    ipv6 = os.environ.get("WG_IPV6", "fd00:6464::1/64")
    ipv4 = os.environ.get("WG_IPV4", "10.0.0.1/24")
    try:
        device = WireguardDevice.get(interface)
        wgconf = device.get_config()
    except Exception as e:
        print(f"Wireguard interface {interface} not found, creating it")
        subprocess.Popen([ "/usr/bin/sudo", "/setup-wg.sh",
            "--name", interface, "--port", port, "--ip6", ipv6, "--ip4", ipv4,
        ])
        while True:
            time.sleep(1)
            try:
                device = WireguardDevice.get(interface)
                wgconf = device.get_config()
                break
            except Exception as e:
                print(f"Wireguard interface {interface} not found, retrying...")

    # Setup NAT64 route
    nat64_prefix = os.environ.get("NAT64_PREFIX", "64:ff9b::/96")
    subprocess.run(["/usr/bin/sudo", "/setup-nat64.sh", "--prefix", nat64_prefix, "--dev", interface], check=True)

    agent_config = Hetznat64AgentConfig(
        wg_interface=interface,
        wg_port=port,
        control_server_hostname=os.environ.get('CONTROL_SERVER_HOSTNAME', 'server'),
        rest_port=int(os.environ.get('PORT', 5001)),
        cert_file=os.environ.get('CERT_FILE', None),
        key_file=os.environ.get('KEY_FILE', None),
        ca_file=os.environ.get('CA_FILE', None),
        api_endpoint=os.environ.get('HCLOUD_API_ENDPOINT', 'https://api.hetzner.cloud/v1'),
        api_key=os.environ.get('HCLOUD_API_TOKEN', None),
        discovery_label_prefix=os.environ.get('DISCOVERY_LABEL_PREFIX', 'hetznat64'),
    )

    agent = Hetznat64Agent(agent_config)
    agent.start()
