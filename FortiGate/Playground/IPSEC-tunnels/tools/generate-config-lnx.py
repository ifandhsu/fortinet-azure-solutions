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
index_end = 10  # Count needs to be less than the IP addresses available in the IP network
vpn_b_gw = "172.16.137.1"
vpn_b_ip_underlay = "172.16.137.10"
# VPN interface IP on FGT needs to be outside out overlay network
#vpn_b_ip_overlay = str(ipaddress.IPv4Network(ip_network_overlay)[-2]) # Reserve last IP in overlay network for FGT
vpn_b_ip_overlay = "10.3.255.254"
vpn_b_subnet = "172.16.138.0/24"
vpn_config_name="VPN1"
bgp_asn="65005"

ip_int_underlay = int(ipaddress.ip_network(ip_network_underlay).network_address)
ip_int_overlay = int(ipaddress.ip_network(ip_network_overlay).network_address)

#################################################################################
# Templates
#################################################################################
template_fgt = """# Generated by /share/tools/generate-config.py
config vpn ipsec phase1-interface
    edit "{{ vpn_config_name }}"
        set type dynamic
        set interface "port2"
        set ike-version 2
        set proposal aes256gcm-prfsha256
        set localid "{{ vpn_config_name }}"
        set mode-cfg enable
        set assign-ip disable
        set dhgrp 21
        set keylife 28800
        set peertype any
        set net-device disable
        set nattraversal forced
        set psksecret {{ vpn_psk }}
    next
end
config vpn ipsec phase2-interface
    edit "{{ vpn_config_name }}"
        set phase1name "{{ vpn_config_name }}"
        set proposal aes256gcm
        set dhgrp 21
        set keylifeseconds 3600
    next
end
config firewall policy
    edit 1
        set name "VPNAcceptAll"
        set srcintf "any"
        set dstintf "any"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set logtraffic all
        set logtraffic-start enable
    next
end
config router static
    edit 3
        set dst {{ vpn_a_ip_underlay }}
        set gateway {{ vpn_b_gw }}
        set device "port2"
    next
    edit 4
        set dst {{ vpn_a_ip_overlay }}
        set device "{{ vpn_config_name }}"
    next
end
config system interface
    edit "{{ vpn_config_name }}"
        set vdom "root"
        set ip {{ vpn_b_ip_overlay }}/32
        set allowaccess ping
        set interface "port2"
    next
end
config router bgp
    set as 65005
    set router-id {{ vpn_b_ip_overlay }}
    set ibgp-multipath enable
    set additional-path enable
    set graceful-restart enable
    config neighbor-group
        edit "branch-peers"
            set advertisement-interval 1
            set capability-graceful-restart enable
            set link-down-failover enable
            set next-hop-self enable
            set soft-reconfiguration enable
            set connect-timer 5
            set remote-as 65005
            set additional-path send
            set route-reflector-client enable
        next
    end
    config neighbor-range
        edit 1
            set prefix {{ vpn_a_ip_overlay }}
            set neighbor-group "branch-peers"
        next
    end
end

"""
template_ifc = """# Generated by /share/tools/generate-config.py
# Adding AnyIP ranges
ip -4 route delete local {{ ip_network_underlay }} dev lo
ip -4 route add local {{ ip_network_underlay }} dev lo
ip -4 route delete local {{ ip_network_overlay }} dev lo
ip -4 route add local {{ ip_network_overlay }} dev lo
ip -4 route add {{ vpn_b_subnet }} via {{ vpn_b_gw }}
"""
template_ipsec = """# Generated by /share/tools/generate-config.py
conn {{ tunnel }}
        rekey=yes
        left={{ vpn_a_ip_underlay }}
        leftsourceip={{ vpn_a_ip_overlay }}
        leftsubnet={{ vpn_a_ip_overlay }}/32
        right={{ vpn_b_ip_underlay }}
        rightsubnet={{ vpn_b_subnet }},{{ vpn_b_ip_overlay }}
        rightid=%any
        ikelifetime=28800s
        lifetime=3600s
        authby=secret
        type=tunnel
        auto=start
        ike=aes256gcm16-prfsha256-ecp521
        esp=aes256gcm16-ecp521
        fragmentation=yes
        dpddelay=3
        dpdtimeout=20
        dpdaction=restart
        keyexchange=ikev2

"""
template_ipsec_secrets = """# Generated by /share/tools/generate-config.py
: PSK "{{ vpn_psk }}"
"""
template_exabgp = """
# index {{ index }}
neighbor {{ vpn_b_ip_overlay }} {                 # Remote neighbor to peer with
    router-id {{ vpn_a_ip_overlay }};              # Our local router-id
    local-address {{ vpn_a_ip_overlay }};          # Our local update-source
    local-as {{ bgp_asn }};                    # Our local AS
    peer-as {{ bgp_asn }};                     # Peer's AS
}
"""
template_exabgpcli = """echo exabgpcli {{ action }} route {{ route }} next-hop {{ vpn_a_ip_overlay }} as-path [ ] local-preference 150
exabgpcli {{ action }} route {{ route }} next-hop {{ vpn_a_ip_overlay }} as-path [ ] local-preference 150

"""

#################################################################################
# Generate FortiGate config
#################################################################################
print("Generate FortiGate config ...")
f = open("/share/tools/build/fgt.conf", "w")

tm = Template(template_fgt)
msg = tm.render(bgp_asn=bgp_asn, vpn_config_name=vpn_config_name, vpn_b_ip_overlay=vpn_b_ip_overlay, vpn_a_ip_underlay=ip_network_underlay, vpn_a_ip_overlay=ip_network_overlay, vpn_b_gw=vpn_b_gw, vpn_psk=vpn_psk)
f.write(msg)

f.close()

#################################################################################
# Generate Linux interface config script using AnyIP
# https://jasonmurray.org/posts/2021/anyip/
#################################################################################
print("Generate Linux interface config script ...")
f = open("/share/tools/build/ifc.sh", "w")
f.write("#!/bin/bash\n")

tm = Template(template_ifc)
msg = tm.render(ip_network_underlay=ip_network_underlay, ip_network_overlay=ip_network_overlay, vpn_b_gw=vpn_b_gw, vpn_b_subnet=vpn_b_subnet)

f.write(msg)

f.close()

#################################################################################
# Generate Linux IPSEC config
#################################################################################
print("Generate Linux IPSEC config file ...")
index = index_start
while index <= index_end:
  vpn_a_ip_underlay = str(ipaddress.IPv4Address(ip_int_underlay + index))
  vpn_a_ip_overlay = str(ipaddress.IPv4Address(ip_int_overlay + index))
  index2 = index % 256                  # secondary interface nr
  index3 = int(index / 256)             # dummy interface nr
  tunnel = "{}{}".format("tunnel", index)

  tm = Template(template_ipsec)
  msg = tm.render(tunnel=tunnel, vpn_a_ip_underlay=vpn_a_ip_underlay, vpn_a_ip_overlay=vpn_a_ip_overlay, vpn_b_ip_underlay=vpn_b_ip_underlay, vpn_b_ip_overlay=vpn_b_ip_overlay, vpn_b_subnet=vpn_b_subnet)
  f = open("/etc/ipsec.d/"+ tunnel + ".conf", "w")
  f.write(msg)
  f.close()

  index += 1

#################################################################################
# Generate Linux IPSEC secrets file
#################################################################################
print("Generate Linux IPSEC secrets file ...")
f = open("/etc/ipsec.secrets", "w")

tm = Template(template_ipsec_secrets)
msg = tm.render(vpn_psk=vpn_psk)

f.write(msg)
f.close()

#################################################################################
# Generate Linux ExaBGP config
#################################################################################
print("Generate Linux ExaBGP config file ...")
page = 1000
index_end_page = ((index_end // page)+1)
index = 1
index2 = index_start
while index <= index_end_page:
  filename = "/etc/exabgp/exabgp" + str(index) + ".conf"
  f = open(filename, "w")
  f.write("# Generated by /share/tools/generate-config.py\n")
  while index2 <= (index*page):
    if index2 > index_end:
      break
    vpn_a_ip_overlay = str(ipaddress.IPv4Address(ip_int_overlay + index2))

    tm = Template(template_exabgp)
    msg = tm.render(index=index2,vpn_b_ip_overlay=vpn_b_ip_overlay, vpn_a_ip_overlay=vpn_a_ip_overlay, bgp_asn=bgp_asn)
    f.write(msg)

    index2 += 1

  f.close()
  index += 1

#################################################################################
# Generate Linux ExaBGP route script
#################################################################################
print("Generate Linux ExaBGP route script ...")

f = open("/share/tools/build/routes-a-add.sh", "w")
f2 = open("/share/tools/build/routes-a-remove.sh", "w")
f3 = open("/share/tools/build/routes-b-add.sh", "w")
f4 = open("/share/tools/build/routes-b-remove.sh", "w")
f.write("# Generated by /share/tools/generate-config.py\n")
f2.write("# Generated by /share/tools/generate-config.py\n")
route_a = "100.0.0.0/24"
route_b = "200.0.0.0/24"
route_a_int = int(ipaddress.ip_network(route_a).network_address)
route_b_int = int(ipaddress.ip_network(route_b).network_address)
index = index_start
while index <= index_end:
  route_a_next = str(ipaddress.IPv4Address(route_a_int + (index * 256))) + "/24"
  route_b_next = str(ipaddress.IPv4Address(route_b_int + (index * 256))) + "/24"
  vpn_a_ip_overlay = str(ipaddress.IPv4Address(ip_int_overlay + index))

  tm = Template(template_exabgpcli)
  msg = tm.render(action="announce",vpn_a_ip_overlay=vpn_a_ip_overlay, route=route_a_next)
  f.write(msg)
  tm = Template(template_exabgpcli)
  msg = tm.render(action="withdraw",vpn_a_ip_overlay=vpn_a_ip_overlay, route=route_a_next)
  f2.write(msg)
  tm = Template(template_exabgpcli)
  msg = tm.render(action="announce",vpn_a_ip_overlay=vpn_a_ip_overlay, route=route_b_next)
  f3.write(msg)
  tm = Template(template_exabgpcli)
  msg = tm.render(action="withdraw",vpn_a_ip_overlay=vpn_a_ip_overlay, route=route_b_next)
  f4.write(msg)

  index += 1

f.close()
f2.close()
f3.close()
f4.close()
