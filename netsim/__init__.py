# netsim/__init__.py
"""netsim -- terminal network topology visualizer. Topo files are trusted Python code."""
from .dsl import NetsimError, cloud, dns, group, host, info, join, label, power, router, send, star, switch

__all__ = ["host", "switch", "router", "dns", "cloud", "group", "join", "star", "power", "label", "send", "info", "NetsimError"]
