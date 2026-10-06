import os
import signal
import tempfile
import textwrap
import unittest
from unittest import mock

from netsim import dsl, log, watch
from netsim.canvas import Canvas
from netsim.layout import layout
from netsim.model import Node
from netsim.render import render

GOOD = """
from netsim import *
a = host("A"); b = switch("B")
join(a, b)
"""


def setUpModule():                      # keep tests out of ~/.netsim
    log.net.sink = log.tool.sink = None


def topo(src):
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(textwrap.dedent(src).lstrip())
    f.close()
    return f.name


def codes(lg):
    return [e.code for e in lg.entries]


class ToolErrors(unittest.TestCase):
    def setUp(self):
        self.files = []

    def tearDown(self):
        for f in self.files:
            os.unlink(f)

    def mk(self, src):
        self.files.append(topo(src))
        return self.files[-1]

    def test_exc_line(self):
        p = self.mk("""
            from netsim import *
            a = host("A")
            join(a, undefined_name)
        """)
        self.assertIsNone(watch.build(p))
        e = log.tool.entries[-1]
        self.assertEqual((e.code, e.where), ("T_EXC", "line 3"))
        self.assertIn("NameError", e.msg)

    def test_unknown_object(self):
        p = self.mk("""
            from netsim import *
            from netsim.model import Node
            a = host("A")
            join(a, Node("ghost", "host"))
        """)
        self.assertIsNone(watch.build(p))
        e = log.tool.entries[-1]
        self.assertEqual((e.code, e.where), ("T_UNKNOWN", "line 4"))

    def _keeps_last_frame(self, target, code):
        good = watch.step(self.mk(GOOD))
        self.assertIsNotNone(good)
        with mock.patch(target, side_effect=RuntimeError("boom")):
            frame = watch.step(self.mk(GOOD), good)
        self.assertIs(frame, good)
        self.assertEqual(codes(log.tool), [code])

    def test_layout_keeps_last_frame(self):
        self._keeps_last_frame("netsim.watch.layout", "T_LAYOUT")

    def test_render_keeps_last_frame(self):
        self._keeps_last_frame("netsim.watch.render", "T_RENDER")


class Cycle(unittest.TestCase):
    def test_cycle_no_link_through_box(self):
        dsl.model.reset()
        a, b, c = dsl.host("A"), dsl.switch("B"), dsl.router("C")
        dsl.join(a, b, c, a)
        signal.alarm(5)                       # render must terminate
        try:
            rects = layout(dsl.model)
            real_box = Canvas.box
            # skip node boxes (fill=True erases what is under them) to expose any line through a box
            with mock.patch.object(Canvas, "box", lambda s, r, title=None, style="", fill=False:
                                   None if fill else real_box(s, r, title, style)):
                cv = render(dsl.model, rects=rects)
        finally:
            signal.alarm(0)
        for nid in dsl.model.nodes:
            x, y, w, h = rects[nid]
            inside = [cv.mask[yy][xx] for yy in range(y + 1, y + h - 1) for xx in range(x + 1, x + w - 1)]
            self.assertFalse(any(inside), f"link drawn through {nid}")
        self.assertIn("┬", render(dsl.model, rects=rects).to_text())   # A-C routed underneath


class Send(unittest.TestCase):
    def setUp(self):
        dsl.model.reset()
        log.net.clear()
        self.pc1, self.sw1, self.r1, self.d1 = (dsl.host("pc1"), dsl.switch("sw1"),
                                                 dsl.router("r1"), dsl.dns("dns1"))
        dsl.join(self.pc1, self.sw1, self.r1, self.d1)

    def test_delivered(self):
        self.assertTrue(dsl.send(self.pc1, self.d1))
        self.assertEqual(codes(log.net), ["N_SEND", "N_HOP", "N_HOP", "N_HOP", "N_DELIVER"])
        self.assertIn("pc1>sw1>r1>dns1 (3 hops)", log.net.entries[-1].msg)

    def test_blocked_by_off_router(self):
        dsl.power(self.r1, "off")
        self.assertFalse(dsl.send(self.pc1, self.d1))
        off = [e for e in log.net.entries if e.code == "N_NODE_OFF"]
        self.assertEqual(len(off), 1)
        self.assertEqual(off[0].where, "r1")
        self.assertEqual(codes(log.net), ["N_NODE_OFF"])

    def test_no_path(self):
        lone = dsl.host("lone")
        self.assertFalse(dsl.send(self.pc1, lone))
        self.assertEqual(codes(log.net), ["N_NOPATH"])

    def test_link_down(self):
        dsl.model.link_between("sw1", "r1").up = False
        self.assertFalse(dsl.send(self.pc1, self.d1))
        self.assertEqual([(e.code, e.where) for e in log.net.entries], [("N_LINK_DOWN", "sw1-r1")])

    def test_down_blocks_send(self):
        dsl.down(self.sw1, self.r1)
        self.assertFalse(dsl.send(self.pc1, self.d1))
        self.assertEqual([(e.code, e.where, e.msg) for e in log.net.entries][-2:],
                         [("N_LINK", "sw1-r1", "sw1-r1 down"), ("N_LINK_DOWN", "sw1-r1", "send pc1>dns1 blocked by down link sw1-r1")])

    def test_up_restores_delivery(self):
        dsl.down(self.r1, self.sw1)
        dsl.up(self.r1, self.sw1)
        self.assertEqual(log.net.entries[-1].msg, "r1-sw1 up")
        self.assertTrue(dsl.send(self.pc1, self.d1))
        self.assertEqual(log.net.entries[-1].code, "N_DELIVER")

    def test_down_up_bad_args(self):
        for fn in (dsl.down, dsl.up):
            with self.assertRaises(dsl.NetsimError) as cm:
                fn(self.pc1, Node("ghost", "host"))
            self.assertEqual(cm.exception.code, "T_UNKNOWN")
            with self.assertRaises(dsl.NetsimError) as cm:
                fn(self.pc1, self.d1)
            self.assertEqual(cm.exception.code, "T_ARGS")


if __name__ == "__main__":
    unittest.main()
