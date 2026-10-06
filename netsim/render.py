# netsim/render.py
"""Model + layout -> Canvas. Draw order: groups, links, nodes, dots."""
import heapq
import os

from . import log
from .canvas import Canvas
from .layout import Rect, collapsed_title, layout, shown

THEME = {"router": "bold cyan", "switch": "bold magenta", "dns": "bold yellow", "host": "bold white",
         "cloud": "bold blue", "on": "green", "off": "red", "idle": "dim", "group": "bright_black",
         "title": "bold", "link": "", "down": "red"}


def _style(key):
    return "" if os.environ.get("NO_COLOR") else THEME.get(key, "")


TURN, CROSS, NEAR, BUSY, MARGIN = 2, 200, 3, 2, 3
STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _attach(r, o):
    """(edge cell, outward step): middle of r's edge facing rect o."""
    h = max(o.x - r.x - r.w, r.x - o.x - o.w)
    v = max(o.y - r.y - r.h, r.y - o.y - o.h)
    if h >= v:
        right = 2 * o.x + o.w > 2 * r.x + r.w
        return (r.x + r.w - 1 if right else r.x, r.y + (r.h - 1) // 2), (1 if right else -1, 0)
    down = 2 * o.y + o.h > 2 * r.y + r.h
    return (r.x + r.w // 2, r.y + r.h - 1 if down else r.y), (0, 1 if down else -1)


class _Grid:
    """Cells a link may use: never a node box; a group border only straight across, in one cell."""

    def __init__(self, model, rects):
        self.box, self.near, self.border = set(), {}, {}   # border: cell -> (group, axis that must not move) or None
        for k, r in rects.items():
            if k in model.nodes or model.groups[k].collapsed:
                self.box |= {(x, y) for x in range(r.x, r.x + r.w) for y in range(r.y, r.y + r.h)}
        for x, y in self.box:                           # keep lines off box edges, prefer mid-gutter
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    c = (x + dx, y + dy)
                    if c not in self.box:
                        self.near[c] = max(self.near.get(c, 0), NEAR if max(abs(dx), abs(dy)) == 1 else 1)
        self.groups = [k for k, g in model.groups.items() if not g.collapsed and k in rects]
        for k in self.groups:
            r = rects[k]
            x2, y2 = r.x + r.w - 1, r.y + r.h - 1
            cells = [((x, y), 0) for x in range(r.x + 1, x2) for y in (r.y, y2)]      # cross vertically
            cells += [((x, y), 1) for y in range(r.y + 1, y2) for x in (r.x, x2)]    # cross horizontally
            for c, axis in cells:
                self.border[c] = None if c in self.border else (k, axis)
            for c in [(r.x, r.y), (x2, r.y), (r.x, y2), (x2, y2)] + [(x, r.y) for x in range(r.x + 2, r.x + 4 + len(k))]:
                self.border[c] = None                   # corners and title text
        for x, y in self.border:                        # light clearance along group borders too
            for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if c not in self.border and c not in self.box:
                    self.near[c] = max(self.near.get(c, 0), 1)
        xs = [v for r in rects.values() for v in (r.x, r.x + r.w)]
        ys = [v for r in rects.values() for v in (r.y, r.y + r.h)]
        self.x0, self.x1, self.y0, self.y1 = min(xs) - MARGIN, max(xs) + MARGIN, min(ys) - MARGIN, max(ys) + MARGIN
        self.top = min(ys)

    def _free(self, c, step, ok):
        if not (self.x0 <= c[0] < self.x1 and self.y0 <= c[1] < self.y1) or c in self.box:
            return False
        if c not in self.border:
            return True
        b = self.border[c]
        return b is not None and (ok is None or b[0] in ok) and step[b[1]] == 0

    def route(self, ra, rb, ok, busy, trunk):
        """route(ra, rb, ok, busy, trunk) -- cells from ra's edge to rb's edge, crossing only borders in ok.
        busy: cells of links sharing no endpoint (cost extra); trunk: cells of links sharing one (cost less)."""
        (sa, da), (tb, db) = _attach(ra, rb), _attach(rb, ra)
        start, into = (sa[0] + da[0], sa[1] + da[1]), (-db[0], -db[1])
        if not self._free(start, da, ok):
            return None
        heap, best, prev, n = [(0, 0, start, da)], {(start, da): 0}, {(start, da): None}, 0
        while heap:
            cost, _, cell, d = heapq.heappop(heap)
            if cost > best[(cell, d)]:
                continue
            if cell == tb:
                out, s = [], (cell, d)
                while s:
                    out.append(s[0])
                    s = prev[s]
                return [sa] + out[::-1]
            for nd in STEPS:
                if nd == (-d[0], -d[1]) or (cell in self.border and nd != d):
                    continue                            # no reversing, no turning on a border
                nxt = (cell[0] + nd[0], cell[1] + nd[1])
                c = cost + 2 - (nxt in trunk) + TURN * (nd != d)
                if nxt == tb:
                    if nd != into:
                        continue
                elif self._free(nxt, nd, ok):
                    c += self.near.get(nxt, 0) + BUSY * (nxt in busy) + CROSS * (nxt in self.border)
                    c += nxt[1] < self.top             # detours prefer the margin below the row
                else:
                    continue
                if c < best.get((nxt, nd), c + 1):
                    best[(nxt, nd)], prev[(nxt, nd)] = c, (cell, d)
                    n += 1
                    heapq.heappush(heap, (c, n, nxt, nd))
        return None


def _mid(cells, border):
    """Straight, non-border cell nearest the middle of a path (for the down marker), else None."""
    inner = [i for i in range(1, len(cells) - 1) if cells[i] not in border
             and (cells[i - 1][0] == cells[i + 1][0] or cells[i - 1][1] == cells[i + 1][1])]
    return cells[min(inner, key=lambda i: abs(2 * i - len(cells)))] if inner else None


def routes(model, rects):
    """routes(model, rects) -- (grid, [(link, cells)]) in link order; cells run edge to edge."""
    grid, out, used = _Grid(model, rects), [], {}         # used: cell -> endpoints of links on it
    members = {k: set(model.flat_members(k)) for k in grid.groups}
    for l in model.links:
        ea, eb = shown(model, l.a), shown(model, l.b)   # links to hidden members attach to the collapsed box
        if ea == eb:
            continue
        ok = {k for k in grid.groups if (l.a in members[k]) != (l.b in members[k])}
        busy = {p for p, ends in used.items() if not ends & {ea, eb}}   # links from one box share a trunk
        trunk = used.keys() - busy
        cells = (grid.route(rects[ea], rects[eb], ok, busy, trunk)
                 or grid.route(rects[ea], rects[eb], None, busy, trunk))
        if cells:
            out.append((l, cells))
            for p in cells[1:-1]:
                used.setdefault(p, set()).update((ea, eb))
    return grid, out


def render(model, ascii=False, rects=None):
    """render(model, ascii=False, rects=None) -- draw the topology onto a new Canvas."""
    rects = rects if rects is not None else layout(model)
    if not rects:
        return Canvas(1, 0, ascii)
    grid, paths = routes(model, rects)

    pts = [p for r in rects.values() for p in ((r.x, r.y), (r.x + r.w - 1, r.y + r.h - 1))]
    pts += [p for _, cells in paths for p in cells]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)   # margin only where a link uses it
    c = Canvas(max(p[0] for p in pts) - x0 + 1, max(p[1] for p in pts) - y0 + 1, ascii)
    rects = {k: Rect(r.x - x0, r.y - y0, r.w, r.h) for k, r in rects.items()}

    for name, g in model.groups.items():
        if g.collapsed or name not in rects:
            continue
        c.box(rects[name], style=_style("group"))
        c.text(rects[name].x + 2, rects[name].y, f" {name} ", _style("title"))

    for l, cells in paths:
        st = _style("link" if l.up else "down")
        c.path([(x - x0, y - y0) for x, y in cells], st)
        m = None if l.up else _mid(cells, grid.border)
        if m:
            c.put(m[0] - x0, m[1] - y0, "x" if ascii else "×", st)

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


def fit(canvas, cols):
    """fit(canvas, cols) -- clip a canvas wider than cols in place, log T_FIT, mark the cut with [+]."""
    if canvas.w <= cols:
        return canvas
    log.tool.add("T_FIT", "render", f"Warning: frame is {canvas.w} columns, terminal has {cols}; clipped")
    canvas.clip(cols)
    canvas.text(max(0, cols - 3), canvas.h // 2, "[+]", _style("title"))
    return canvas


def status(model, ascii=False):
    """status(model) -- one-line summary of the legend, sizes and log counts."""
    on, off = ("*", "o") if ascii else ("●", "○")
    n, t = log.net.counts(), log.tool.counts()
    return (f"{on} on {off} off | {len(model.nodes)}n {len(model.links)}l | "
            f"NET {n['E']}E {n['W']}W | TOOL {t['E']}E")
