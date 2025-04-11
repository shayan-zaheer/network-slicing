from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

class SmartCityTopo(Topo):
    def build(self):
        # Core Switch (Backbone of the Network)
        core_switch = self.addSwitch("s1")

        # Services with their Subnets & Host Counts
        services = {
            "Traffic":  ("10.1.0.", 2),
            "Healthcare": ("10.2.0.", 2),
            "PublicSafety": ("10.3.0.", 2),
            "EnergyGrid": ("10.4.0.", 2),
            "SmartHomes": ("10.5.0.", 2),
            "Education": ("10.6.0.", 2)
        }

        # Create sub-switches and connect hosts
        for i, (service, (subnet, host_count)) in enumerate(services.items(), start=2):
            switch = self.addSwitch(f"s{i}")  # Each service gets a switch
            self.addLink(core_switch, switch)  # Connect service switch to core switch
            
            for j in range(1, host_count + 1):
                host_ip = f"{subnet}{j}/24"
                host = self.addHost(f"h{service[:2]}{j}", ip=host_ip)
                self.addLink(host, switch)  # Connect host to its service switch

def run():
    setLogLevel("info")
    net = Mininet(topo=SmartCityTopo(), controller=Controller, switch=OVSSwitch)
    
    net.start()
    print("Smart City Topology is Up!")
    
    CLI(net)  # Open Mininet CLI
    net.stop()

if __name__ == "__main__":
    run()
