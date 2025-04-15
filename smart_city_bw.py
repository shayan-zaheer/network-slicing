from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch, Node
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.node import RemoteController
import os
import time

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

def configure_qos(net):
    """Configure QoS on all switches in the network"""
    print("\n⚙️ Configuring QoS settings for all switches...")
    
    # Create the QoS configuration script
    script_path = "/tmp/qos_config.py"
    with open(script_path, 'w') as f:
        f.write('''
#!/usr/bin/env python3

import subprocess
import re
import sys
from time import sleep

def run_cmd(cmd):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing command: {cmd}")
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()

def configure_switch_qos(switch_name):
    """Configure QoS on a specific switch."""
    print(f"\\n🔧 Configuring QoS for switch {switch_name}...")
    
    # Get the switch's interfaces
    interfaces_output = run_cmd(f"ovs-vsctl list-ports {switch_name}")
    if not interfaces_output:
        print(f"Failed to get interfaces for {switch_name}")
        return False
    
    interfaces = interfaces_output.split('\\n')
    
    # Create QoS policy on each interface
    for interface in interfaces:
        if not interface.strip():
            continue
            
        print(f"  ⚙️  Setting up QoS on interface {interface}")
        
        # Clear any existing QoS configurations
        run_cmd(f"ovs-vsctl clear port {interface} qos")
        
        # Create QoS policy with HTB (Hierarchical Token Bucket)
        run_cmd(f"ovs-vsctl -- set port {interface} qos=@newqos -- "
                f"--id=@newqos create qos type=linux-htb "
                f"other-config:max-rate=1000000000 " # 1 Gbps total bandwidth
                f"queues=0=@q0,1=@q1,2=@q2,3=@q3,4=@q4,5=@q5 -- "
                f"--id=@q0 create queue other-config:min-rate=100000000 other-config:max-rate=1000000000 -- " # Default: 100 Mbps min, 1 Gbps max
                f"--id=@q1 create queue other-config:min-rate=400000000 other-config:max-rate=800000000 -- "    # Healthcare: 400 Mbps min, 800 Mbps max (highest priority)
                f"--id=@q2 create queue other-config:min-rate=300000000 other-config:max-rate=700000000 -- "    # Public Safety: 300 Mbps min, 700 Mbps max
                f"--id=@q3 create queue other-config:min-rate=200000000 other-config:max-rate=500000000 -- "    # Energy Grid: 200 Mbps min, 500 Mbps max
                f"--id=@q4 create queue other-config:min-rate=100000000 other-config:max-rate=300000000 -- "    # Smart Homes: 100 Mbps min, 300 Mbps max
                f"--id=@q5 create queue other-config:min-rate=50000000 other-config:max-rate=200000000")        # Education: 50 Mbps min, 200 Mbps max
    
    # Verify QoS configuration
    print(f"  ✅ QoS configuration completed for {switch_name}")
    return True

def main():
    """Configure QoS for all switches in the network."""
    print("🌆 Smart City QoS Configuration Tool")
    print("====================================")
    
    # Get all switches
    switches_output = run_cmd("ovs-vsctl list-br")
    if not switches_output:
        print("Failed to get switches. Is Open vSwitch running?")
        return 1
    
    switches = switches_output.split('\\n')
    
    # Configure each switch
    for switch in switches:
        if not switch.strip():
            continue
        configure_switch_qos(switch)
    
    # Verify QoS configuration
    print("\\n🔍 QoS Configuration Summary:")
    for switch in switches:
        if not switch.strip():
            continue
        qos_info = run_cmd(f"ovs-vsctl list qos")
        queue_info = run_cmd(f"ovs-vsctl list queue")
        
        if qos_info:
            qos_count = len(re.findall(r"_uuid", qos_info))
            print(f"  - {switch}: {qos_count} QoS policies configured")
        
        if queue_info:
            queue_count = len(re.findall(r"_uuid", queue_info))
            print(f"    with {queue_count} queues")
    
    print("\\n✅ QoS configuration completed successfully!")
    print("Queue priorities:")
    print("  Queue 1: Healthcare (400 Mbps min, 800 Mbps max)")
    print("  Queue 2: Public Safety (300 Mbps min, 700 Mbps max)")
    print("  Queue 3: Energy Grid (200 Mbps min, 500 Mbps max)")
    print("  Queue 4: Smart Homes (100 Mbps min, 300 Mbps max)")
    print("  Queue 5: Education (50 Mbps min, 200 Mbps max)")
    print("  Queue 0: Default (100 Mbps min, 1 Gbps max)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
        ''')
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    
    # Run the QoS configuration script
    os.system(f"python3 {script_path}")
    
    print("QoS configuration completed.")

def run():
    setLogLevel("info")
    
    # Create network with OVS switches supporting QoS
    net = Mininet(
        topo=SmartCityTopo(), 
        controller=None, 
        autoSetMacs=True,
        switch=OVSSwitch
    )
    
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
    for host in net.hosts:
        if host.name != "r1":
            subnet_base = host.IP().rsplit('.', 1)[0]
            gateway_ip = subnet_base + '.1'
            host.cmd(f"ip route add default via {gateway_ip}")
    # Configure QoS on all switches
    print("Waiting for controller to establish connection...")
    time.sleep(5)  # Give controller time to connect
    configure_qos(net)

    print("\n🚀 Smart City Network with QoS is Up!")
    print("Services with priority bandwidth allocation:")
    print("  - Healthcare: 400-800 Mbps (Queue 1)")
    print("  - Public Safety: 300-700 Mbps (Queue 2)")
    print("  - Energy Grid: 200-500 Mbps (Queue 3)")
    print("  - Smart Homes: 100-300 Mbps (Queue 4)")
    print("  - Education: 50-200 Mbps (Queue 5)")
    print("  - Default: 100-1000 Mbps (Queue 0)")
    
    # Run some initial ping tests to establish connections

    
    # Open Mininet CLI
    CLI(net)
    
    # Cleanup
    net.stop()

if __name__ == "__main__":
    run()