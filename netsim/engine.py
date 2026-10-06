"""Packet delivery: BFS paths, send diagnostics, and one recorded Event per send."""
import random
from collections import deque
from dataclasses import dataclass, field

from . import log


@dataclass
class Packet:
    src: str
    dst: str
    ttl: int = 16
    proto: str = "icmp"


@dataclass
class Event:
    """Event -- one send as anim.py replays it. path runs src..last node reached;
    latency[i] is the ms of link path[i]-path[i+1]; at/reason are set when dropped."""
    index: int
    src: str
    dst: str
    path: list
    latency: list = field(default_factory=list)
    outcome: str = "delivered"          # or "dropped"
    at: str | None = None               # drop node
    reason: str = ""


def _record(model, pkt, p, at=None, reason=""):
    lat = [model.link_between(x, y).latency for x, y in zip(p, p[1:])]
    model.events.append(Event(len(model.events), pkt.src, pkt.dst, list(p), lat,
                              "dropped" if at else "delivered", at, reason))


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
    """send(model, pkt) -- deliver or diagnose, logging to the net log and model.events. True if delivered.
    Link loss draws from a Random seeded by the send index, so a reload repeats the result."""
    tag = f"{pkt.src}>{pkt.dst}"
    p = path(model, pkt.src, pkt.dst)
    if p and len(p) - 1 > pkt.ttl:
        log.net.add("N_TTL", p[pkt.ttl], f"send {tag} ttl {pkt.ttl} expired")
        _record(model, pkt, p[: pkt.ttl + 1], p[pkt.ttl], "ttl expired")
        return False
    if p:
        rng = random.Random(len(model.events))
        for i, (x, y) in enumerate(zip(p, p[1:])):
            if rng.random() < model.link_between(x, y).loss:
                log.net.add("N_LOSS", x, f"send {tag} dropped at {x} (loss on {x}-{y})")
                _record(model, pkt, p[: i + 1], x, f"loss on {x}-{y}")
                return False
        log.net.add("N_SEND", pkt.src, f"send {tag} {pkt.proto}")
        for x, y in zip(p, p[1:]):
            log.net.add("N_HOP", y, f"{tag} {x}>{y}")
        log.net.add("N_DELIVER", pkt.dst, f"{tag} via {'>'.join(p)} ({len(p) - 1} hops)")
        _record(model, pkt, p)
        return True
    p = path(model, pkt.src, pkt.dst, power=False)
    if p:
        off = next(n for n in p if not model.nodes[n].on)
        log.net.add("N_NODE_OFF", off, f"send {tag} dropped at {off} (off)")
        _record(model, pkt, p[: p.index(off) + 1], off, "off")
        return False
    p = path(model, pkt.src, pkt.dst, power=False, links=False)
    if p:
        a, b = next((x, y) for x, y in zip(p, p[1:]) if not model.link_between(x, y).up)
        log.net.add("N_LINK_DOWN", f"{a}-{b}", f"send {tag} blocked by down link {a}-{b}")
        _record(model, pkt, p[: p.index(a) + 1], a, f"link down {a}-{b}")
    else:
        log.net.add("N_NOPATH", pkt.src, f"send {tag} no path")
        _record(model, pkt, [pkt.src], pkt.src, "no path")
    return False
