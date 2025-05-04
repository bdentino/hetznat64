from dataclasses import dataclass
import socket
from flask import Flask, request, jsonify
from wireguard_tools import WireguardConfig, WireguardDevice, WireguardKey, WireguardPeer
from ipaddress import ip_interface, IPv4Interface, IPv6Interface
import os

@dataclass
class Hetznat64AgentConfig:
    wg_interface: str
    wg_port: int
    control_server_hostname: str
    control_server_port: int
    rest_port: int = 5001
    cert_file: str = None
    key_file: str = None

class Hetznat64Agent:
    def __init__(self, config: Hetznat64AgentConfig):
        self.__config = config
        self.__wg_key = None
        self.__app = Flask(__name__)
        self.__setup_routes()

    def start(self):
        self.__app.run(port=self.__config.rest_port, host='::', ssl_context=(self.__config.cert_file, self.__config.key_file) if self.__config.cert_file and self.__config.key_file else None)

    def stop(self):
        self.__app.stop()

    def __setup_routes(self):
        @self.__app.route('/handshake', methods=['POST'])
        def handshake():
            data = request.json
            agent_ip = data.get('agent_ip')
            control_ip = data.get('control_ip')
            public_key = data.get('public_key')
            preshared_key = data.get('preshared_key', None)
            print("data", data)

            if not self.__wg_key:
                self.__wg_key = WireguardKey.generate()

            # Extract prefix from control_ip and apply to agent_ip
            control_prefix = str(ip_interface(control_ip).network)
            agent_ip_addr = ip_interface(agent_ip).ip
            new_agent_ip = f"{agent_ip_addr}/{control_prefix.split('/')[-1]}"

            # Update IP using sudo script
            import subprocess
            subprocess.run(["/usr/bin/sudo", "/update-ip.sh", str(ip_interface(new_agent_ip))], check=True)

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
                endpoint_port=self.__config.control_server_port,
                allowed_ips=[control_ip],
            ))

            print(config.to_wgconfig(wgquick_format=True))
            WireguardDevice.get(self.__config.wg_interface).set_config(config)

            response = {
                'public_key': str(self.__wg_key.public_key()),
                'port': self.__config.wg_port,
            }
            return jsonify(response), 200

if __name__ == "__main__":
    import subprocess, time
    interface = os.environ.get("WG_INTERFACE", "hetznat64")
    ipv6 = os.environ.get("WG_IPV6", "fd00:6464::1/64")
    port = os.environ.get("WG_PORT", "51820")
    try:
        device = WireguardDevice.get(interface)
        wgconf = device.get_config()
    except Exception as e:
        print(f"Wireguard interface {interface} not found, creating it")
        subprocess.Popen([
            "/usr/bin/sudo",
            "/setup-wg.sh",
            "--name", interface,
            "--port", port,
            "--ip6", ipv6,
            "--ip4", os.environ.get("WG_IPV4", "10.0.0.1/24"),
        ])
        while True:
            time.sleep(1)
            try:
                device = WireguardDevice.get(interface)
                wgconf = device.get_config()
                break
            except Exception as e:
                print(f"Wireguard interface {interface} not found, retrying...")

    port = wgconf.listen_port
    agent_config = Hetznat64AgentConfig(
        wg_interface=interface,
        wg_port=port,
        control_server_hostname=os.environ.get('CONTROL_SERVER_HOSTNAME', 'server'),
        control_server_port=int(os.environ.get('CONTROL_SERVER_PORT', 51820)),
        rest_port=int(os.environ.get('PORT', 5001)),
        cert_file=os.environ.get('CERT_FILE', None),
        key_file=os.environ.get('KEY_FILE', None),
    )

    agent = Hetznat64Agent(agent_config)
    agent.start()
