from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch, Node
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.node import RemoteController

class SmartCityTopo(Topo):
    def build(self):
        # Add Router (Acts as Gateway for all subnets)
        router = self.addHost("r1", ip="10.1.0.1/24")

        # Define Services with Subnets & Hosts
        services = {
            "Traffic":  ("10.1.0.", "10.1.0.1/24", 8),
            "Healthcare": ("10.2.0.", "10.2.0.1/24", 8),
            "PublicSafety": ("10.3.0.", "10.3.0.1/24", 8),
            "EnergyGrid": ("10.4.0.", "10.4.0.1/24", 8),
            "SmartHomes": ("10.5.0.", "10.5.0.1/24", 8),
            "Education": ("10.6.0.", "10.6.0.1/24", 8)
        }

        # Create Sub-switches and Connect Hosts
        for i, (service, (subnet, gw, host_count)) in enumerate(services.items(), start=2):
            switch = self.addSwitch(f"s{i}")  # Each service gets a dedicated switch
            self.addLink(router, switch)  # Connect service switch to the router
            
            # Create Hosts
            for j in range(2, host_count + 2):
                host_ip = f"{subnet}{j}/24"
                host = self.addHost(f"h{service[:2]}{j-1}", ip=host_ip, defaultRoute=f"via {gw}")
                self.addLink(host, switch)  # Connect host to its service switch

def run():
    setLogLevel("info")
    net = Mininet(topo=SmartCityTopo(), controller=None, autoSetMacs=True)
    # Add remote controller (Ryu listens on 127.0.0.1:6653)
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    # Start Network
    net.start()
    
    
    # Enable IP Forwarding on the Router
    router = net.get("r1")
    router.cmd("sysctl -w net.ipv4.ip_forward=1")

    # Attach subnet interfaces to the router
    subnets = {
        "10.2.0.1/24": "r1-eth1",
        "10.3.0.1/24": "r1-eth2",
        "10.4.0.1/24": "r1-eth3",
        "10.5.0.1/24": "r1-eth4",
        "10.6.0.1/24": "r1-eth5"
    }
    
    for ip, iface in subnets.items():
        router.cmd(f"ifconfig {iface} {ip}")

    print("🚀 Smart City Subnet-based Topology is Up!")
    
    CLI(net)  # Open Mininet CLI
    net.stop()

if __name__ == "__main__":
    run()
