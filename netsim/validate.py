"""Post-exec checks; warnings go to the net log."""
from . import log


def validate(model):
    """validate(model) -- warn N_ISOLATED (no links) and N_GW_MISSING (no gw, no router)."""
    linked = {x for l in model.links for x in (l.a, l.b)}
    for nid in model.nodes:
        if nid not in linked:
            log.net.add("N_ISOLATED", nid, f"{nid} has no links")
    for name, g in model.groups.items():
        ids = model.flat_members(name)
        if not g.gw and ids and not any(model.nodes[i].kind == "router" for i in ids):
            log.net.add("N_GW_MISSING", name, f"group {name} has no gateway, using {ids[0]}")
