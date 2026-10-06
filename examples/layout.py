from netsim import *

pc1 = host("PC1")
pc2 = host("PC2")
sw1 = switch("SW1")
r1 = router("R1")

r2 = router("R2")
dns1 = dns("DNS1")
cloud1 = cloud("Internet")

server = host("SERVER")
pc3 = host("PC3")


# Nested group
join(r1, server)
servers = group("SERVERS", server, kind="lan")



# LAN
join(pc1, sw1)
join(pc2, sw1)
join(sw1, r1)
lan = group("LAN1", pc1, pc2, sw1, r1, kind="lan", gw=r1)

# WAN
join(r1, r2)
join(r2, cloud1)
wan = group("WAN1", r2, cloud1, kind="wan", gw=r2)

# Cycle
join(r2, dns1)
join(dns1, r1)

# PC3 deliberately remains loose/unconnected
