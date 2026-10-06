# netsim/layout.py
"""Layout: BFS layers per group (a layer is a column), nested groups as blocks, top level by adjacency."""
from typing import NamedTuple

NODE_W, NODE_H, GAP, VGAP, PAD = 10, 4, 6, 1, 2


class Rect(NamedTuple):
    x: int
    y: int
    w: int
    h: int


def shown(model, nid):
    """shown(model, nid) -- the outermost collapsed group holding nid, else nid itself."""
    out, p = nid, model.nodes[nid].parent
    while p:
        out = p if model.groups[p].collapsed else out
        p = model.groups[p].parent
    return out


def collapsed_title(model, name):
    """collapsed_title(model, name) -- "NAME (n)" with the number of devices inside."""
    return f"{name} ({len(model.flat_members(name))})"


def _climb(model, key, units):
    """Walk up from a node to the first ancestor (or itself) in units, else None."""
    while key is not None and key not in units:
        key = (model.nodes[key] if key in model.nodes else model.groups[key]).parent
    return key


def _bfs(model, units, start, seen):
    """Layers of units reachable from start via links; seen is updated (visited set for cycles)."""
    idx = {u: i for i, u in enumerate(units)}
    adj = {u: set() for u in units}
    for l in model.links:
        a, b = _climb(model, l.a, idx), _climb(model, l.b, idx)
        if a is not None and b is not None and a != b:
            adj[a].add(b)
            adj[b].add(a)
    layers, frontier = [], [start]
    seen.add(start)
    while frontier:
        layers.append(frontier)
        nxt = []
        for u in frontier:
            for v in sorted(adj[u], key=idx.get):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return layers


def _shift(rels, dx, dy):
    return {k: Rect(r.x + dx, r.y + dy, r.w, r.h) for k, r in rels.items()}


def _block(model, key):
    """(w, h, anchor, {id: Rect} relative to the block); anchor = y of the first node row."""
    if key in model.nodes:
        return NODE_W, NODE_H, 0, {key: Rect(0, 0, NODE_W, NODE_H)}
    g = model.groups[key]
    if g.collapsed:
        w = max(NODE_W, len(collapsed_title(model, key)) + 6)
        return w, NODE_H, 0, {key: Rect(0, 0, w, NODE_H)}
    units, seen = list(g.members), set()
    start = _climb(model, g.gw, units) if g.gw else None
    cols = _bfs(model, units, start or units[0], seen)
    rest = [u for u in units if u not in seen]          # disconnected members: final column
    cols = [[_block(model, u) for u in col] for col in cols + ([rest] if rest else [])]
    top = max(col[0][2] for col in cols)
    rels, x, bottom = {}, PAD, PAD
    for col in cols:
        y = PAD + top - col[0][2]                       # line up first rows across columns
        for w, h, _, r in col:
            rels.update(_shift(r, x, y))
            y += h + VGAP
        bottom = max(bottom, y - VGAP)
        x += max(b[0] for b in col) + GAP
    w, h = x - GAP + PAD, bottom + PAD
    rels[key] = Rect(0, 0, w, h)
    return w, h, PAD + top, rels


def _structure(model):
    return (tuple((k, n.parent) for k, n in model.nodes.items()),
            tuple((k, tuple(g.members), g.gw, g.parent, g.collapsed) for k, g in model.groups.items()),
            tuple((l.a, l.b) for l in model.links))


_cache = {}


def layout(model):
    """layout(model) -- {id: Rect} for visible nodes and groups; cached on structure only."""
    key = _structure(model)
    if key not in _cache:
        _cache.clear()
        _cache[key] = _layout(model)
    return dict(_cache[key])


def _layout(model):
    order = list(model.nodes)

    def first(k):
        return order.index(k) if k in model.nodes else min(
            (order.index(i) for i in model.flat_members(k)), default=len(order))

    top = sorted([k for k, n in model.nodes.items() if not n.parent]
                 + [k for k, g in model.groups.items() if not g.parent], key=first)
    seq, seen = [], set()
    for k in top:                                       # adjacency order, declaration order breaks ties
        if k not in seen:
            seq += [u for layer in _bfs(model, top, k, seen) for u in layer]
    blocks = [_block(model, k) for k in seq]
    anchor = max((b[2] for b in blocks), default=0)
    rects, x = {}, 0
    for w, h, a, r in blocks:
        rects.update(_shift(r, x, anchor - a))
        x += w + GAP
    return rects
