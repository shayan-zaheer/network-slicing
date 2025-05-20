import ipaddress
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet, ethernet, ipv4, ether_types
from ryu.ofproto import ofproto_v1_3
import socketio
import threading
import time
from ryu.lib import hub

class SmartCityController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SmartCityController, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.dpid_name_map = {
            1: "Traffic Control Switch",
            2: "Healthcare Switch",
            3: "Public Safety Switch",
            4: "Energy Grid Switch",
            5: "Smart Homes Switch",
            6: "Education Switch",
        }

        # Define networks once at initialization
        self.healthcare_network = '10.2.0.0/24'
        self.public_safety_network = '10.3.0.0/24'
        self.energy_grid_network = '10.4.0.0/24'
        self.smart_homes_network = '10.5.0.0/24'
        self.education_network = '10.6.0.0/24'
        self.sio = socketio.Client()
        self.sio.connect('http://localhost:5000')

        threading.Thread(target=self.poll_stats, daemon=True).start()
        self.traffic_counter = {}  # Dictionary to track total packets per IP
        hub.spawn(self.emit_top_talkers)

    def poll_stats(self):
        while True:
            for dp in self.datapaths.values():
                ofproto = dp.ofproto
                parser = dp.ofproto_parser
                req = parser.OFPFlowStatsRequest(dp)
                dp.send_msg(req)
            time.sleep(3)
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        total_flows = len(body)
        total_bytes = sum(flow.byte_count for flow in body)
        total_packets = sum(flow.packet_count for flow in body)

        dpid = ev.msg.datapath.id
        name = self.dpid_name_map.get(dpid, f"Switch {dpid}")
        bandwidth_mbps = ((total_bytes * 8) / (1024 * 1024)) / 10

        # Accumulate packet counts per source IP
        for flow in body:
            match = flow.match
            src_ip = match.get('ipv4_src')
            if src_ip:
                self.traffic_counter[src_ip] = self.traffic_counter.get(src_ip, 0) + flow.packet_count

        self.sio.emit('flow_stats', {
            'dpid': dpid,
            'name': name,
            'flows': total_flows,
            'bandwidth': round(bandwidth_mbps, 2),
            'packets': total_packets
        })

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Store datapath for future use
        self.datapaths[datapath.id] = datapath
        
        # Clear existing flows
        self.clear_flows(datapath)
        
        # Default flow: send unmatched packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=inst,
            idle_timeout=0,  # NEVER timeout
            hard_timeout=0   # NEVER timeout
        )
        datapath.send_msg(mod)
        self.logger.info(f"Switch {datapath.id} connected. Installed default flow to send unmatched packets to controller.")
    def emit_top_talkers(self):
        while True:
            top_talkers = sorted(self.traffic_counter.items(), key=lambda item: item[1], reverse=True)[:3]
            self.logger.info(f"Top Talkers: {top_talkers}")
            self.sio.emit('top_talkers', {'top': top_talkers})
            self.reset_inactive_traffic()
            hub.sleep(5)
            
    def reset_inactive_traffic(self):
        """Reset traffic counter for inactive IPs after a certain time interval."""
        current_time = time.time()

        # Check for inactive IPs and reset their counters
        for ip, last_seen in list(self.traffic_counter.items()):
            print(ip, last_seen)
            if current_time - last_seen > 10:  # 10 seconds inactivity threshold
                self.traffic_counter[ip] = 0
                self.logger.info(f"Reset traffic counter for inactive IP: {ip}")
                
    def clear_flows(self, datapath):
        """Clear all existing flow entries from a datapath."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Create a flow mod message to delete all flows
        match = parser.OFPMatch()
        instructions = []
        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=match,
            instructions=instructions
        )
        datapath.send_msg(flow_mod)
        self.logger.info(f"Cleared all flows from switch {datapath.id}")

    def add_flow(self, datapath, priority, match, actions, idle_timeout=30, hard_timeout=60):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,  
            hard_timeout=hard_timeout   
        )
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        # Parse packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        # Skip non-IP packets (including LLDP)
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.logger.debug("ARP packet received, flooding to all ports")
            self.send_packet_out(datapath, msg, in_port, ofproto.OFPP_FLOOD)
            return
        if eth.ethertype != ether_types.ETH_TYPE_IP:
            self.logger.info(f"Ignored non-IP packet: ethertype={hex(eth.ethertype)}")
            return
        # Extract IPv4 header
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            return
        # Source and destination IP addresses
        src_ip = ip_pkt.src
        dst_ip = ip_pkt.dst
        
        # Determine traffic type based on IP subnets
        if self.is_in_network(src_ip, self.healthcare_network) or self.is_in_network(dst_ip, self.healthcare_network):
            # Highest priority for healthcare traffic
            self.logger.info(f"Healthcare traffic detected: {src_ip} -> {dst_ip}")
            self.install_priority_flow(datapath, src_ip, dst_ip, in_port, queue_id=1, priority=200)
            
        elif self.is_in_network(src_ip, self.public_safety_network) or self.is_in_network(dst_ip, self.public_safety_network):
            # High priority for public safety
            self.logger.info(f"Public Safety traffic detected: {src_ip} -> {dst_ip}")
            self.install_priority_flow(datapath, src_ip, dst_ip, in_port, queue_id=2, priority=150)
            
        elif self.is_in_network(src_ip, self.energy_grid_network) or self.is_in_network(dst_ip, self.energy_grid_network):
            # Medium-high priority for energy grid
            self.logger.info(f"Energy Grid traffic detected: {src_ip} -> {dst_ip}")
            self.install_priority_flow(datapath, src_ip, dst_ip, in_port, queue_id=3, priority=100)
            
        elif self.is_in_network(src_ip, self.smart_homes_network) or self.is_in_network(dst_ip, self.smart_homes_network):
            # Medium priority for smart homes
            self.logger.info(f"Smart Homes traffic detected: {src_ip} -> {dst_ip}")
            self.install_priority_flow(datapath, src_ip, dst_ip, in_port, queue_id=4, priority=80)
            
        elif self.is_in_network(src_ip, self.education_network) or self.is_in_network(dst_ip, self.education_network):
            # Standard priority for education
            self.logger.info(f"Education traffic detected: {src_ip} -> {dst_ip}")
            self.install_priority_flow(datapath, src_ip, dst_ip, in_port, queue_id=5, priority=60)
            
        else:
            # Default priority for other traffic
            self.logger.info(f"Regular traffic detected: {src_ip} -> {dst_ip}")
            self.install_default_flow(datapath, src_ip, dst_ip, in_port)
        
        # Forward the packet that triggered this PacketIn
        self.send_packet_out(datapath, msg, in_port, ofproto.OFPP_FLOOD)

    def is_in_network(self, ip, network_cidr):
        """Check if an IP address is within a specific network."""
        try:
            network = ipaddress.IPv4Network(network_cidr, strict=False)
            return ipaddress.IPv4Address(ip) in network
        except ValueError:
            self.logger.error(f"Invalid IP address or network: {ip}, {network_cidr}")
            return False

    def install_priority_flow(self, datapath, src_ip, dst_ip, in_port, queue_id, priority):
        """Install a flow rule with QoS for specific traffic."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Match on IP addresses
        match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=src_ip,
            ipv4_dst=dst_ip
        )
        
        # Set QoS queue and forward normally
        actions = [
            parser.OFPActionSetQueue(queue_id),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL)
        ]
        
        # Add bidirectional flow rules with 30-second timeout
        self.add_flow(datapath, priority, match, actions)
        
        # Add reverse flow for response traffic
        match_reverse = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=dst_ip,
            ipv4_dst=src_ip
        )
        self.add_flow(datapath, priority, match_reverse, actions, idle_timeout=30, hard_timeout=60)

    def install_default_flow(self, datapath, src_ip, dst_ip, in_port):
        """Install default flow rule for regular traffic."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Match on IP addresses
        match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=src_ip,
            ipv4_dst=dst_ip
        )
        
        # Forward normally without specific QoS
        actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
        
        # Add flow with shorter timeout
        self.add_flow(datapath, 50, match, actions)
        
        # Add reverse flow
        match_reverse = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=dst_ip,
            ipv4_dst=src_ip
        )
        self.add_flow(datapath, 50, match_reverse, actions, idle_timeout=20, hard_timeout=40)

    def send_packet_out(self, datapath, msg, in_port, output_port):
        """Send a packet out a specific port."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
            
        actions = [parser.OFPActionOutput(output_port)]
        
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)