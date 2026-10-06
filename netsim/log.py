# netsim/log.py
"""Two log channels (net, tool) sharing one Entry type and one CODES table."""
import os
from collections import Counter, deque
from dataclasses import dataclass

CODES = {
    "N_CREATE": ("I", "device or link created"), "N_LINK": ("I", "link created"),
    "N_SEND": ("I", "packet sent"), "N_HOP": ("I", "hop traversed"), "N_DELIVER": ("I", "delivered"),
    "N_LOSS": ("E", "dropped by link loss"), "N_DROP": ("E", "dropped"),
    "N_NODE_OFF": ("E", "blocked by powered-off node"), "N_LINK_DOWN": ("E", "link down"),
    "N_NOPATH": ("E", "no path"), "N_NOROUTE": ("E", "no route"), "N_TTL": ("E", "TTL expired"),
    "N_DNS_NX": ("E", "DNS lookup failed"), "N_SUBNET": ("W", "subnet mismatch"),
    "N_ISOLATED": ("W", "node with no links"), "N_GW_MISSING": ("W", "group has no gateway, fallback used"),
    "T_SYNTAX": ("E", "compile error"), "T_EXC": ("E", "exception in topo file"),
    "T_TIMEOUT": ("E", "exec exceeded limit"), "T_NAME": ("E", "duplicate name"),
    "T_UNKNOWN": ("E", "unknown object"), "T_ARGS": ("E", "bad argument"),
    "T_LAYOUT": ("E", "layout failed"), "T_RENDER": ("E", "renderer crashed, last good frame kept"),
    "T_IO": ("E", "file missing or unreadable"), "T_ERROR": ("E", "other tool error"),
}


@dataclass
class Entry:
    t: float
    lvl: str
    code: str
    where: str
    msg: str

    def __str__(self):
        return f"t={self.t:.2f} {self.lvl} {self.code} {self.where or '-'} {self.msg}"


class Log:
    def __init__(self, name, cap=200, sink=None):
        self.name, self.sink, self.entries = name, sink, deque(maxlen=cap)

    def add(self, code, where="", msg="", t=0.0):
        """add(code, where, msg, t) -- record an entry; level comes from CODES."""
        e = Entry(t, CODES.get(code, ("E",))[0], code, where, msg)
        self.entries.append(e)
        if self.sink:
            try:
                os.makedirs(os.path.dirname(self.sink), exist_ok=True)
                with open(self.sink, "a") as f:
                    f.write(str(e) + "\n")
            except OSError:
                pass
        return e

    def counts(self):
        """counts() -- Counter of levels, e.g. {'E': 1, 'W': 2}."""
        return Counter(e.lvl for e in self.entries)

    def clear(self):
        self.entries.clear()


net = Log("net")
tool = Log("tool", sink=os.path.expanduser("~/.netsim/tool.log"))
