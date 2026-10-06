# netsim/layout.py
"""Naive layout: every node in one row, groups wrap their members."""
from typing import NamedTuple

NODE_W, NODE_H, GAP = 10, 4, 6


class Rect(NamedTuple):
    x: int
    y: int
    w: int
    h: int


def _depth(model, name):
    d = 0
    while name:
        d, name = d + 1, model.groups[name].parent
    return d


def layout(model):
    """layout(model) -- {id: Rect} for nodes and groups (one shared namespace)."""
    D = max((_depth(model, g) for g in model.groups), default=0)
    node_y = 2 * D
    order = list(model.nodes)
    rects, visited = {}, set()

    def first(key):
        return order.index(key) if key in model.nodes else min(
            (order.index(i) for i in model.flat_members(key)), default=len(order))

    def place(key, x):
        if key in visited:
            return 0
        visited.add(key)
        if key in model.nodes:
            rects[key] = Rect(x, node_y, NODE_W, NODE_H)
            return NODE_W
        g, d = model.groups[key], _depth(model, key)
        cx = x + 2
        for m in g.members:
            w = place(m, cx)
            cx += w + GAP if w else 0
        inner = max(cx - GAP - (x + 2), 2)
        rects[key] = Rect(x, 2 * (d - 1), inner + 4, NODE_H + 4 * (D - d + 1))
        return inner + 4

    top = [k for k, n in model.nodes.items() if not n.parent] + [k for k, g in model.groups.items() if not g.parent]
    x = 0
    for key in sorted(top, key=first):
        w = place(key, x)
        x += w + GAP if w else 0
    return rects
