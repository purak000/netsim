from netsim import *

pc1 = host("PC1")
pc2 = host("PC2")
sw1 = switch("SW1")
r1 = router("R1")

join(pc1, sw1, r1)
join(pc2, sw1)
lan = group("LAN1", pc1, pc2, sw1)
label(pc1, "10.0.1")
