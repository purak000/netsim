"""Packet delivery: BFS paths and send diagnostics. No timing in v0.1."""
from collections import deque
from dataclasses import dataclass

from . import log


@dataclass
class Packet:
    src: str
    dst: str
    ttl: int = 16
    proto: str = "icmp"


def path(model, a, b, power=True, links=True):
    """path(model, a, b) -- shortest node-id list a..b, or None.
    power/links=False ignore off nodes / down links (used for diagnostics)."""
    ok = lambda n: not power or model.nodes[n].on
    if not (ok(a) and ok(b)):
        return None
    prev, queue, visited = {}, deque([a]), {a}
    while queue:
        cur = queue.popleft()
        if cur == b:
            out = [b]
            while out[-1] != a:
                out.append(prev[out[-1]])
            return out[::-1]
        for l in model.links:
            if cur not in (l.a, l.b) or (links and not l.up):
                continue
            nxt = l.b if cur == l.a else l.a
            if nxt not in visited and ok(nxt):
                visited.add(nxt)
                prev[nxt] = cur
                queue.append(nxt)
    return None


def send(model, pkt):
    """send(model, pkt) -- deliver or diagnose, logging to the net log. True if delivered."""
    tag = f"{pkt.src}>{pkt.dst}"
    p = path(model, pkt.src, pkt.dst)
    if p and len(p) - 1 > pkt.ttl:
        log.net.add("N_TTL", p[pkt.ttl], f"send {tag} ttl {pkt.ttl} expired")
        return False
    if p:
        log.net.add("N_SEND", pkt.src, f"send {tag} {pkt.proto}")
        for x, y in zip(p, p[1:]):
            log.net.add("N_HOP", y, f"{tag} {x}>{y}")
        log.net.add("N_DELIVER", pkt.dst, f"{tag} via {'>'.join(p)} ({len(p) - 1} hops)")
        return True
    p = path(model, pkt.src, pkt.dst, power=False)
    if p:
        off = next(n for n in p if not model.nodes[n].on)
        log.net.add("N_NODE_OFF", off, f"send {tag} dropped at {off} (off)")
        return False
    p = path(model, pkt.src, pkt.dst, power=False, links=False)
    if p:
        a, b = next((x, y) for x, y in zip(p, p[1:]) if not model.link_between(x, y).up)
        log.net.add("N_LINK_DOWN", f"{a}-{b}", f"send {tag} blocked by down link {a}-{b}")
    else:
        log.net.add("N_NOPATH", pkt.src, f"send {tag} no path")
    return False
