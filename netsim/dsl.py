# netsim/dsl.py
"""DSL functions exec'd from topology files; they build into `model`."""
from . import engine, log
from .docs import category, info
from .model import Group, Link, Model, Node

model = Model()


class NetsimError(Exception):
    """NetsimError(code, msg) -- raised by DSL functions; code is a key of CODES."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


def _new_name(name):
    if not isinstance(name, str) or not name:
        raise NetsimError("T_ARGS", f"Error: name must be a non-empty string, got {name!r}")
    if name in model.nodes or name in model.groups:
        raise NetsimError("T_NAME", f"Error: device '{name}' already exists")


def _device(name, kind):
    _new_name(name)
    n = model.nodes[name] = Node(name, kind)
    return n


@category("devices")
def host(name):
    """host(name) -- create an end host."""
    return _device(name, "host")


@category("devices")
def switch(name):
    """switch(name) -- create a switch."""
    return _device(name, "switch")


@category("devices")
def router(name):
    """router(name) -- create a router (preferred group gateway)."""
    return _device(name, "router")


@category("devices")
def dns(name):
    """dns(name) -- create a DNS server."""
    return _device(name, "dns")


@category("devices")
def cloud(name):
    """cloud(name) -- create a cloud (Internet, WAN)."""
    return _device(name, "cloud")


def _resolve(x, fn):
    """Node or Group -> node id (groups resolve to their gateway)."""
    if isinstance(x, Node) and model.nodes.get(x.id) is x:
        return x.id
    if isinstance(x, Group) and model.groups.get(x.name) is x:
        return model.gateway(x.name)[0]
    raise NetsimError("T_UNKNOWN", f"Error: {fn}() got unknown object {x!r}")


@category("wiring")
def group(name, *members, kind="lan", gw=None, collapsed=False):
    """group(name, *members, kind="lan", gw=None, collapsed=False) -- box devices/groups together.
    Members are devices or groups; a member can belong to one group only."""
    _new_name(name)
    if not members:
        raise NetsimError("T_ARGS", f"Error: group '{name}' needs at least one member")
    ids = []
    for m in members:
        if not isinstance(m, (Node, Group)) or (model.nodes.get(getattr(m, "id", None)) is not m
                                               and model.groups.get(getattr(m, "name", None)) is not m):
            raise NetsimError("T_UNKNOWN", f"Error: group() got unknown object {m!r}")
        key = m.id if isinstance(m, Node) else m.name
        if m.parent:
            raise NetsimError("T_ARGS", f"Error: '{key}' is already in group '{m.parent}'")
        ids.append(key)
    g = Group(name, kind, ids, None, None, bool(collapsed))
    model.groups[name] = g
    for m in members:
        m.parent = name
    if gw is not None:
        gid = _resolve(gw, "group")
        if gid not in model.flat_members(name):
            raise NetsimError("T_ARGS", f"Error: gateway '{gid}' is not a member of '{name}'")
        g.gw = gid
    return g


@category("wiring")
def join(*items, latency=0, loss=0.0):
    """join(a, b, ..., latency=0, loss=0.0) -- link items in a chain; groups use their gateway."""
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0:
        raise NetsimError("T_ARGS", f"Error: latency must be >= 0, got {latency!r}")
    if isinstance(loss, bool) or not isinstance(loss, (int, float)) or not 0 <= loss <= 1:
        raise NetsimError("T_ARGS", "Error: loss must be between 0 and 1")
    ids = [_resolve(x, "join") for x in items]
    out = []
    for a, b in zip(ids, ids[1:]):
        if a == b:
            raise NetsimError("T_ARGS", f"Error: cannot link '{a}' to itself")
        out.append(Link(a, b, latency, loss))
        model.links.append(out[-1])
    return out


@category("wiring")
def star(center, *leaves):
    """star(center, *leaves) -- link every leaf to center."""
    return [join(center, leaf)[0] for leaf in leaves]


@category("state")
def power(x, state="on"):
    """power(x, "on"|"off") -- switch a device on or off."""
    if state not in ("on", "off"):
        raise NetsimError("T_ARGS", f"Error: power state must be 'on' or 'off', got {state!r}")
    if not isinstance(x, Node):
        raise NetsimError("T_UNKNOWN", f"Error: power() got unknown object {x!r}")
    model.nodes[_resolve(x, "power")].on = state == "on"
    return x


@category("state")
def label(x, text):
    """label(x, text) -- second line of text in the device box."""
    if not isinstance(x, Node):
        raise NetsimError("T_UNKNOWN", f"Error: label() got unknown object {x!r}")
    model.nodes[_resolve(x, "label")].meta["label"] = str(text)
    return x


def _set_link(a, b, up, fn):
    if not (isinstance(a, Node) and isinstance(b, Node)):
        raise NetsimError("T_UNKNOWN", f"Error: {fn}() needs two devices, got {a!r}, {b!r}")
    ia, ib = _resolve(a, fn), _resolve(b, fn)
    l = model.link_between(ia, ib)
    if l is None:
        raise NetsimError("T_ARGS", f"Error: no link between '{ia}' and '{ib}'")
    l.up = up
    log.net.add("N_LINK", f"{ia}-{ib}", f"{ia}-{ib} {'up' if up else 'down'}")
    return l


@category("state")
def down(a, b):
    """down(a, b) -- take the link between devices a and b down.
    Sends after this line that need the link fail with N_LINK_DOWN."""
    return _set_link(a, b, False, "down")


@category("state")
def up(a, b):
    """up(a, b) -- bring the link between devices a and b back up."""
    return _set_link(a, b, True, "up")


@category("traffic")
def send(a, b, ttl=16, proto="icmp"):
    """send(a, b, ttl=16, proto="icmp") -- send one packet now; results go to the net log.
    Runs when called; put power()/down() before it. Returns True if delivered."""
    return engine.send(model, engine.Packet(_resolve(a, "send"), _resolve(b, "send"), ttl, proto))


EXPORTS = ["host", "switch", "router", "dns", "cloud", "group", "join", "star", "power", "label", "down", "up", "send", "info", "NetsimError"]


def namespace():
    """namespace() -- dict of DSL names injected into the topo file."""
    g = globals()
    return {k: g[k] for k in EXPORTS}
