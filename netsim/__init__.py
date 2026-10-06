# netsim/__init__.py
"""netsim -- terminal network topology visualizer. Topo files are trusted Python code."""
from .dsl import NetsimError, cloud, dns, down, group, host, info, join, label, power, router, send, star, switch, up

__all__ = ["host", "switch", "router", "dns", "cloud", "group", "join", "star", "power", "label", "down", "up", "send", "info", "NetsimError"]
