import unittest

from netsim import dsl, log
from netsim.anim import DOT, STEP, Timeline
from netsim.render import render

from test_layout import GOLDEN, chain, collapsed, cycle, nested, star


def setUpModule():                      # keep tests out of ~/.netsim
    log.net.sink = log.tool.sink = None


def lit(tl, t):
    return tl.state(t)


class Anim(unittest.TestCase):
    def setUp(self):
        dsl.model.reset()
        log.net.clear()

    def test_hops_light_in_order(self):
        a, b, c = dsl.host("A"), dsl.switch("B"), dsl.router("C")
        dsl.join(a, b, latency=100)
        dsl.join(b, c)                  # 0 ms uses the default step
        self.assertTrue(dsl.send(a, c))
        ev = dsl.model.events[0]
        self.assertEqual((ev.path, ev.latency, ev.outcome), (["A", "B", "C"], [100, 0], "delivered"))
        tl = Timeline.build(dsl.model.events)
        self.assertEqual([(round(t, 3), n, k) for t, n, k in tl.entries],
                         [(0.0, "A", "hop"), (0.1, "B", "hop"), (round(0.1 + STEP, 3), "C", "hop")])
        self.assertEqual(lit(tl, 0.05), {"A": "hop"})
        self.assertEqual(lit(tl, 0.1 + STEP + 0.01), {"B": "hop", "C": "hop"})
        self.assertEqual(lit(tl, 0.1 + DOT + 0.01), {"C": "hop"})
        self.assertEqual(lit(tl, 0.1 + STEP + DOT), {})

    def test_drop_lights_red_at_drop_node(self):
        pc, r1, d1 = dsl.host("pc1"), dsl.router("r1"), dsl.dns("dns1")
        dsl.join(pc, r1, d1)
        dsl.power(r1, "off")
        self.assertFalse(dsl.send(pc, d1))
        ev = dsl.model.events[0]
        self.assertEqual((ev.path, ev.outcome, ev.at, ev.reason), (["pc1", "r1"], "dropped", "r1", "off"))
        tl = Timeline.build(dsl.model.events)
        self.assertEqual(tl.entries[-1], (STEP, "r1", "drop"))
        self.assertEqual(lit(tl, DOT + 0.01), {"r1": "drop"})
        text = render(dsl.model, ascii=True, now=DOT + 0.01).to_text()
        self.assertIn("x", text)        # red drop dot on r1 only
        self.assertNotIn("x", render(dsl.model, ascii=True).to_text())

    def test_now_none_matches_goldens(self):
        for build in (chain, star, nested, collapsed, cycle):
            dsl.model.reset()
            build()
            text = render(dsl.model, now=None).to_text() + "\n"
            self.assertEqual(text, (GOLDEN / f"{build.__name__}.txt").read_text(), build.__name__)

    def topo(self):
        dsl.model.reset()
        log.net.clear()
        a, b, c = dsl.host("A"), dsl.switch("B"), dsl.host("C")
        dsl.join(a, b, c, loss=0.5)
        return [dsl.send(a, c) for _ in range(12)], [(e.path, e.at) for e in dsl.model.events]

    def test_loss_is_deterministic(self):
        first, second = self.topo(), self.topo()
        self.assertEqual(first, second)
        self.assertIn(True, first[0])   # seed gives a mix, so the test exercises both outcomes
        self.assertIn(False, first[0])
        self.assertIn("N_LOSS", [e.code for e in log.net.entries])
        self.assertIn("N_LOSS", log.CODES)


if __name__ == "__main__":
    unittest.main()
