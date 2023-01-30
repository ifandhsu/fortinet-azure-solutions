#!/usr/bin/env python3

from jinja2 import Template
import ipaddress

#################################################################################
# Variables
#################################################################################
ip_network_underlay = "10.1.0.0/16"
ip_network_overlay = "10.2.0.0/16"
vpn_psk = "fortinet"
index_start = 1   # First IP in the IP network range to start counting
index_end = 1000  # Count needs to be less than the IP addresses available in the IP network
port3_gw = "172.16.138.1"
vpn_b_ip = "172.16.137.10"
vpn_b_subnet = "172.16.138.0/24"

ip_int_overlay = int(ipaddress.ip_network(ip_network_overlay).network_address)
index = index_start
end = index_end

#################################################################################
# Templates
#################################################################################
template_smokeping = """
*** Targets ***

probe = FPing

menu = Top
title = Network Latency Grapher
remark = Remark \
	 Remark2

+ VPN
menu = VPN
title = VPN

++ group0
menu = group0
title = group0
{% for i in range(index_start, index_end) %}
{% if i is divisibleby 256 %}
++ group{{ i }}
menu = group{{ i }}
title = group{{ i }}
{% endif %}
+++ tunnel{{ i }}
menu = {{ ipaddress.IPv4Address(i|int + ip_int_overlay|int) }}
title = {{ ipaddress.IPv4Address(i|int + ip_int_overlay|int) }}
host = {{ ipaddress.IPv4Address(i|int + ip_int_overlay|int) }}
{% endfor %}
"""
template_ifc = """# Generated by /share/tools/generate-config.py
# Adding AnyIP ranges
ip -4 route add {{ ip_network_underlay }} via {{ port3_gw }}
ip -4 route add {{ ip_network_overlay }} via {{ port3_gw }}
"""

#################################################################################
# Generate Smokeping config
#################################################################################
print("Generate Smokeping config ...")
f = open("/share/smokeping/config/Targets", "w")

tm = Template(template_smokeping)
msg = tm.render(index_start=index_start, index_end=index_end, ip_int_overlay=ip_int_overlay, ipaddress=ipaddress)
f.write(msg)

f.close()

#################################################################################
# Generate Linux interface config script
#################################################################################
print("Generate Linux interface config script ...")
f = open("/share/tools/build/ifc.sh", "w")
f.write("#!/bin/bash\n")

tm = Template(template_ifc)
msg = tm.render(ip_network_underlay=ip_network_underlay, ip_network_overlay=ip_network_overlay, port3_gw=port3_gw)

f.write(msg)

f.close()

#################################################################################