import os
import pathlib
import signal
import unittest

from netsim import dsl, log
from netsim.layout import layout
from netsim.render import fit, render, routes

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden"


def setUpModule():                      # keep tests out of ~/.netsim
    log.net.sink = log.tool.sink = None


def chain():
    dsl.join(dsl.host("PC1"), dsl.switch("SW1"), dsl.router("R1"))


def star():
    sw = dsl.switch("SW1")
    dsl.star(sw, dsl.host("PC1"), dsl.host("PC2"), dsl.host("PC3"))


def nested():
    pc1, pc2, sw1, r1 = dsl.host("PC1"), dsl.host("PC2"), dsl.switch("SW1"), dsl.router("R1")
    srv, r2 = dsl.host("SERVER"), dsl.router("R2")
    dsl.join(pc1, sw1, r1, srv)
    dsl.join(pc2, sw1)
    dsl.join(r1, r2)
    lan = dsl.group("LAN1", pc1, pc2, sw1, r1, gw=r1)
    servers = dsl.group("SERVERS", srv, gw=srv)
    dsl.group("SITE", lan, servers, gw=r1)


def collapsed():
    pc1, pc2, sw1, r1 = dsl.host("PC1"), dsl.host("PC2"), dsl.switch("SW1"), dsl.router("R1")
    r2 = dsl.router("R2")
    dsl.join(pc1, sw1, r1, r2)
    dsl.join(pc2, sw1)
    dsl.group("LAN1", pc1, pc2, sw1, r1, gw=r1, collapsed=True)


def cycle():
    a, b, c = dsl.host("A"), dsl.switch("B"), dsl.router("C")
    dsl.join(a, b, c, a)
    dsl.group("RING", a, b, c, gw=a)


class Golden(unittest.TestCase):
    def check(self, build):
        dsl.model.reset()
        build()
        signal.alarm(5)                   # layout and render must terminate
        try:
            text = render(dsl.model).to_text() + "\n"
        finally:
            signal.alarm(0)
        path = GOLDEN / f"{build.__name__}.txt"
        if os.environ.get("NETSIM_UPDATE_GOLDEN"):
            path.write_text(text)
        self.assertEqual(text, path.read_text())

    def test_chain(self):
        self.check(chain)

    def test_star(self):
        self.check(star)

    def test_nested(self):
        self.check(nested)

    def test_collapsed(self):
        self.check(collapsed)

    def test_cycle(self):
        self.check(cycle)


def detour():
    a, b, c = dsl.host("A"), dsl.switch("B"), dsl.host("C")
    dsl.join(a, b, c)
    dsl.join(a, c)                      # B sits between A and C on the row


def wide():
    dsl.join(*[dsl.host(f"H{i}") for i in range(6)])


class Routing(unittest.TestCase):
    def paths(self, build):
        dsl.model.reset()
        build()
        rects = layout(dsl.model)
        grid, out = routes(dsl.model, rects)
        self.assertEqual(len(out), len(dsl.model.links))
        for l, cells in out:            # rules 1 and 2 for every link
            ra, rb = rects[l.a], rects[l.b]
            self.assertTrue(all(c not in grid.box for c in cells[1:-1]), (l.a, l.b))
            for r, end in ((ra, cells[0]), (rb, cells[-1])):
                x, y = end
                self.assertTrue(x in (r.x, r.x + r.w - 1) or y in (r.y, r.y + r.h - 1))
                self.assertTrue(x == r.x + r.w // 2 or y == r.y + (r.h - 1) // 2)
            for g in grid.groups:
                inside = {l.a, l.b} & set(dsl.model.flat_members(g))
                hits = [i for i, c in enumerate(cells) if grid.border.get(c, (None,))[0] == g]
                self.assertEqual(len(hits), 1 if len(inside) == 1 else 0, (l.a, l.b, g))
                for i in hits:          # straight across
                    p, q = cells[i - 1], cells[i + 1]
                    self.assertTrue(p[0] == q[0] or p[1] == q[1])
        return {(l.a, l.b): cells for l, cells in out}

    def test_detour(self):
        cells = self.paths(detour)[("A", "C")]
        self.assertGreater(len({x for x, _ in cells}), 2)
        self.assertGreater(len({y for _, y in cells}), 1)   # left the row to get around B

    def test_cycle(self):
        signal.alarm(5)
        try:
            out = self.paths(cycle)
        finally:
            signal.alarm(0)
        self.assertEqual(len(out), 3)

    def test_nested_crosses_borders_once(self):
        self.paths(nested)

    def test_wider_than_terminal(self):
        dsl.model.reset()
        wide()
        log.tool.clear()
        c = render(dsl.model)
        self.assertGreater(c.w, 80)
        fit(c, 80)
        self.assertEqual(c.w, 80)
        self.assertEqual([e.code for e in log.tool.entries], ["T_FIT"])
        self.assertEqual(log.tool.entries[0].lvl, "W")
        self.assertIn("[+]", c.to_text().splitlines()[c.h // 2][-3:])


class Stable(unittest.TestCase):
    def test_state_changes_keep_positions(self):
        dsl.model.reset()
        nested()
        m = dsl.model
        before = layout(m)
        dsl.power(m.nodes["R1"], "off")
        dsl.down(m.nodes["R1"], m.nodes["R2"])
        dsl.send(m.nodes["PC1"], m.nodes["R2"])
        self.assertEqual(layout(m), before)
        dsl.model.reset()               # fresh structure must agree with the cached result
        nested()
        self.assertEqual(layout(dsl.model), before)


if __name__ == "__main__":
    unittest.main()
