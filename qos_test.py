#!/usr/bin/env python3

import time
from requests import get
"""
Smart City QoS Testing Script
This script tests QoS functionality by running bandwidth tests between different service types.
Run this from the Mininet CLI using: source qos_test.py
"""

# Test healthcare priority
print("\n=== Testing Healthcare Priority (should get 400-800 Mbps) ===")
print("Starting iperf server on healthcare host...")
h_server = "hHe1"  # Healthcare host
h_client = "hTr1"  # Traffic host
print(f"Testing bandwidth from {h_client} to {h_server}...")
h_server = get(h_server)  # Get healthcare host from Mininet
h_client = get(h_client)  # Get traffic host from Mininet

# Start iperf server
h_server.cmd("iperf -s -u &")  # UDP server for better QoS testing
time.sleep(1)

# Run iperf client test
print(h_client.cmd(f"iperf -c {h_server.IP()} -u -b 1000M -t 5"))

# Test public safety priority
print("\n=== Testing Public Safety Priority (should get 300-700 Mbps) ===")
ps_server = "hPu1"  # Public safety host
print(f"Testing bandwidth from {h_client} to {ps_server}...")
ps_server = get(ps_server)

# Start iperf server
ps_server.cmd("iperf -s -u &")
time.sleep(1)

# Run iperf client test
print(h_client.cmd(f"iperf -c {ps_server.IP()} -u -b 1000M -t 5"))

# Test education (lowest priority)
print("\n=== Testing Education Priority (should get 50-200 Mbps) ===")
ed_server = "hEd1"  # Education host
print(f"Testing bandwidth from {h_client} to {ed_server}...")
ed_server = get(ed_server)

# Start iperf server
ed_server.cmd("iperf -s -u &")
time.sleep(1)

# Run iperf client test
print(h_client.cmd(f"iperf -c {ed_server.IP()} -u -b 1000M -t 5"))

# Clean up iperf servers
h_server.cmd("pkill -f iperf")
ps_server.cmd("pkill -f iperf")
ed_server.cmd("pkill -f iperf")

print("\n=== QoS Testing Complete ===")