# netsim/render.py
"""Model + layout -> Canvas. Draw order: groups, links, nodes, dots."""
import os

from . import log
from .canvas import Canvas
from .layout import collapsed_title, layout, shown

THEME = {"router": "bold cyan", "switch": "bold magenta", "dns": "bold yellow", "host": "bold white",
         "cloud": "bold blue", "on": "green", "off": "red", "idle": "dim", "group": "bright_black",
         "title": "bold", "link": "", "down": "red"}


def _style(key):
    return "" if os.environ.get("NO_COLOR") else THEME.get(key, "")


def render(model, ascii=False, rects=None):
    """render(model, ascii=False, rects=None) -- draw the topology onto a new Canvas."""
    rects = rects if rects is not None else layout(model)
    nodes = [rects[k] for k in model.nodes if k in rects]
    base = max((r.y + r.h for r in rects.values()), default=0)
    routes = []
    for l in model.links:
        ea, eb = shown(model, l.a), shown(model, l.b)   # links to hidden members attach to the collapsed box
        if ea == eb:
            continue
        a, b = sorted((rects[ea], rects[eb]), key=lambda r: r.x)
        between = any(a.x < r.x < b.x for r in nodes)
        routes.append((l, a, b, between))
    lanes = sum(1 for *_, far in routes if far)
    c = Canvas(max((r.x + r.w for r in rects.values()), default=1), base + lanes + (1 if lanes else 0), ascii)

    for name, g in model.groups.items():
        if g.collapsed or name not in rects:
            continue
        c.box(rects[name], style=_style("group"))
        c.text(rects[name].x + 2, rects[name].y, f" {name} ", _style("title"))

    lane = base
    for l, a, b, far in routes:
        st = _style("link" if l.up else "down")
        if not far:                                  # neighbours: straight line between sides
            y = a.y + 1
            c.hline(a.x + a.w - 1, b.x, y, st)
            if b.y + 1 != y:
                c.vline(b.x - 1, y, b.y + 1, st)
        else:                                        # route under the row: down, across, up
            ax, bx = a.x + a.w // 2, b.x + b.w // 2
            c.vline(ax, a.y + a.h - 1, lane, st)
            c.hline(ax, bx, lane, st)
            c.vline(bx, lane, b.y + b.h - 1, st)
            lane += 1
        if not l.up:
            mx = (a.x + a.w + b.x) // 2 if not far else (a.x + b.x + b.w) // 2
            c.put(mx, a.y + 1 if not far else lane - 1, "x" if ascii else "×", st)

    for k, n in model.nodes.items():
        r = rects.get(k)
        if not r:
            continue
        c.box(r, fill=True)
        name = n.id[: r.w - 2]
        c.text(r.x + (r.w - len(name)) // 2, r.y + 1, name, _style(n.kind))
        c.text(r.x + 2, r.y + 2, n.meta.get("label", "")[: r.w - 4])
        on, off, idle = ("*", "o", ".") if ascii else ("●", "○", "●")
        c.put(r.x + 1, r.y + 2, on if n.on else off, _style("on" if n.on else "off"))
        c.put(r.x + r.w - 2, r.y + 2, idle, _style("idle"))
    for name, g in model.groups.items():
        if g.collapsed and name in rects:
            c.box(rects[name], style=_style("group"), fill=True)
            c.text(rects[name].x + 2, rects[name].y, f" {collapsed_title(model, name)} ", _style("title"))
    return c


def status(model, ascii=False):
    """status(model) -- one-line summary of the legend, sizes and log counts."""
    on, off = ("*", "o") if ascii else ("●", "○")
    n, t = log.net.counts(), log.tool.counts()
    return (f"{on} on {off} off | {len(model.nodes)}n {len(model.links)}l | "
            f"NET {n['E']}E {n['W']}W | TOOL {t['E']}E")
