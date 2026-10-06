# netsim/model.py
"""Topology model. Knows nothing about display."""
from dataclasses import dataclass, field


@dataclass(eq=False)
class Node:
    id: str
    kind: str
    on: bool = True
    parent: str | None = None          # innermost group name
    meta: dict = field(default_factory=dict)


@dataclass(eq=False)
class Group:
    name: str
    kind: str = "lan"
    members: list = field(default_factory=list)   # node ids and group names
    gw: str | None = None
    parent: str | None = None
    collapsed: bool = False


@dataclass(eq=False)
class Link:
    a: str
    b: str
    latency: float = 0
    loss: float = 0.0
    bandwidth: float | None = None
    up: bool = True


@dataclass
class Model:
    nodes: dict = field(default_factory=dict)     # id -> Node, declaration order
    groups: dict = field(default_factory=dict)    # name -> Group
    links: list = field(default_factory=list)

    def reset(self):
        """reset() -- clear in place so references held by the DSL stay valid."""
        self.nodes.clear(); self.groups.clear(); self.links.clear()

    def link_between(self, a, b):
        """link_between(a, b) -- the Link joining two node ids, or None."""
        return next((l for l in self.links if {l.a, l.b} == {a, b}), None)

    def flat_members(self, name, seen=None):
        """flat_members(name) -- node ids inside a group, recursively, in order."""
        seen = set() if seen is None else seen
        out = []
        for m in self.groups[name].members:
            if m in seen:
                continue
            seen.add(m)
            out += self.flat_members(m, seen) if m in self.groups else [m]
        return out

    def gateway(self, name):
        """gateway(name) -- (node id, used_fallback): gw, else first router, else first member."""
        g = self.groups[name]
        if g.gw:
            return g.gw, False
        ids = self.flat_members(name)
        routers = [i for i in ids if self.nodes[i].kind == "router"]
        return (routers or ids)[0], True
