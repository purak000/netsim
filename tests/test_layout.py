import os
import pathlib
import signal
import unittest

from netsim import dsl, log
from netsim.layout import layout
from netsim.render import render

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
