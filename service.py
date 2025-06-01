import os
import time
import requests
import subprocess
import hcloud
from ipaddress import ip_interface, IPv4Interface, IPv6Interface
from dataclasses import dataclass

from hcloud.servers import BoundServer
from wireguard_tools import WireguardConfig, WireguardDevice, WireguardKey, WireguardPeer

@dataclass
class WireguardServerConfig:
  # Name of the wireguard interface (must be unique on the server)
  name: str

  # Local ipv6 address to assign the wireguard interface
  ip: IPv4Interface | IPv6Interface

  # Port to listen on
  port: int

  # key for the wireguard server
  key: WireguardKey

@dataclass(kw_only=True)
class Hetznat64Config:
  # Wireguard server config
  wireguard: WireguardServerConfig

  # Hetzner Cloud API
  api_endpoint: str = "https://api.hetzner.cloud/v1"
  api_key: str

  # Prefix for the labels which servers will assign themselves
  # in order to get picked up by this service's discovery mechanism
  discovery_label_prefix: str = "hetznat64"

  # Interval in seconds at which the service should poll the Hetzner Cloud API
  poll_interval: int = 5

  # Path to the CA certificate
  ca_file: str = None

  # Path to the server's certificate
  cert_file: str = None

  # Path to the server's key
  key_file: str = None


class Hetznat64Service:
  def __init__(self, config: Hetznat64Config):
    self.__config = config
    self.__hcloud = hcloud.Client(token=config.api_key, api_endpoint=config.api_endpoint)
    self.__server = None


  def start(self):
    print("Starting Hetznat64 service with config:")
    if not self.__server:
      interface = self.__config.wireguard.name
      addresses = [self.__config.wireguard.ip]
      config = WireguardConfig(
        private_key=self.__config.wireguard.key,
        listen_port=self.__config.wireguard.port,
        addresses=addresses,
      )

      self.__server = WireguardDevice.get(interface)
      print(interface, self.__server)
      print('getting devices')
      self.__server.set_config(config)
      for dev in WireguardDevice.list():
        print("getting config for device", dev.interface)
        print(dev.get_config().to_wgconfig(wgquick_format=True))
      print('got devices')

    while True:
      self.poll()
      time.sleep(self.__config.poll_interval)

  def stop(self):
    self.__server.close()

  def poll(self):
    label = f'{self.__config.discovery_label_prefix}.status=waiting'
    servers: list[BoundServer] = []
    index = 1
    while True:
      page = self.__hcloud.servers.get_list(label_selector=label, page=index)
      index += 1
      servers.extend(page.servers)
      if not page.meta.pagination.next_page:
        break

    device = WireguardDevice.get(self.__config.wireguard.name)
    config = device.get_config()
    config.addresses = [self.__config.wireguard.ip]
    config.private_key = self.__config.wireguard.key
    oldconfig = config.to_wgconfig(wgquick_format=True)
    for server in servers:
      server_id = (server.id + 8) & 0xFFFFFFFF
      network = self.__config.wireguard.ip.network
      ipv6 = f"{network[0].exploded[:-9]}{(server_id >> 16) & 0xFFFF:04x}:{server_id & 0xFFFF:04x}"
      peer_ip = IPv6Interface(ipv6)

      # Delete any peers with the same wireguard ip
      peer_key = next((p for p in config.peers.keys() if peer_ip in config.peers[p].allowed_ips), None)
      if peer_key:
        config.del_peer(peer_key)

      # Delete any peers with the same endpoint ip
      endpoint_host = IPv6Interface(server.public_net.ipv6.ip).ip
      endpoint_peers = [p for p in config.peers.keys() if config.peers[p].endpoint_host == endpoint_host]
      for peer_key in endpoint_peers:
        config.del_peer(peer_key)

      # Services on hetzner servers with a ::/64 address will actually be listening on ::1
      if endpoint_host.exploded.endswith(":0000"):
          endpoint_host = IPv6Interface(endpoint_host.exploded[:-2] + "1").ip
      print(f"Server {server.id} with IP {endpoint_host} is waiting for handshake (peer ip: {peer_ip})")
      try:
          response = requests.post(
              f"https://[{endpoint_host}]:5001/handshake",
              json={
                  'control_ip': str(self.__config.wireguard.ip),
                  'control_port': self.__config.wireguard.port,
                  'public_key': str(self.__config.wireguard.key.public_key()),
                  'agent_ip': str(peer_ip),
              },
              timeout=10,
              cert=(self.__config.cert_file, self.__config.key_file),
              verify=self.__config.ca_file,
          )
          if response.status_code == 200:
              data = response.json()
              public_key = data['public_key']
              endpoint_port = data['port']
          else:
              print(f"Handshake failed with status {response.status_code}")
              continue
      except Exception as e:
          print(f"Failed to connect to agent: {e}")
          continue
      config.add_peer(WireguardPeer(
        public_key=public_key,
        endpoint_host=endpoint_host,
        endpoint_port=endpoint_port,
        persistent_keepalive=25,
        allowed_ips=[ipv6],
      ));

    if oldconfig != config.to_wgconfig(wgquick_format=True):
      print(config.to_wgconfig(wgquick_format=True))
      WireguardDevice.get(self.__config.wireguard.name).set_config(config)

    updated = WireguardDevice.get(self.__config.wireguard.name).get_config()
    for peer in updated.peers.values():
      if not peer.last_handshake:
        try:
          ping_result = subprocess.run(
            ["ping6", "-c", "1", "-W", "5", str(peer.allowed_ips[0].ip)],
            capture_output=True
          )
          if ping_result.returncode == 0:
            print(f"Ping to {peer.allowed_ips[0].ip} succeeded")
          else:
            print(f"Ping to {peer.allowed_ips[0].ip} failed")
        except Exception as e:
          print(f"Ping process failed for {peer.allowed_ips[0].ip}: {e}")
    else:
      print("No changes to the config")



if __name__ == "__main__":
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

  # set the wireguard interface to the ipv6 address
  subprocess.run(["/usr/bin/sudo", "/update-ip.sh", str(ip_interface(ipv6))], check=True)

  # set the nat64 interface to the ipv6 address
  nat64_prefix = os.environ.get("NAT64_PREFIX", "64:ff9b::/96")
  nat64_ipv6 = os.environ.get("NAT64_IPV6", "fd00:6464:64:ff9b::64")
  subprocess.run(["/usr/bin/sudo", "/setup-nat64.sh", "--prefix", nat64_prefix, "--via", nat64_ipv6], check=True)

  wgkey = WireguardKey.generate()
  service = Hetznat64Service(
    Hetznat64Config(
      wireguard=WireguardServerConfig(name=interface, ip=ip_interface(ipv6), port=port, key=wgkey),
      discovery_label_prefix=os.environ.get("DISCOVERY_LABEL_PREFIX", 'hetznat64'),
      api_endpoint=os.environ.get("HCLOUD_API_ENDPOINT", 'https://api.hetzner.cloud/v1'),
      api_key=os.environ["HCLOUD_API_TOKEN"],
      cert_file=os.environ["CERT_FILE"],
      key_file=os.environ["KEY_FILE"],
      ca_file=os.environ["CA_FILE"],
    )
  )
  print(f'Starting service on port {port} with key {wgkey.public_key()}')
  service.start()
