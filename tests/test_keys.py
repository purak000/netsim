import unittest

from netsim.canvas import Canvas
from netsim.keys import PAN_X, State, handle, parse
from netsim.render import fit


class Keys(unittest.TestCase):
    def test_pause_freezes_and_resume_continues(self):
        st = State(t0=10.0)
        st = handle(" ", st, 12.0)
        self.assertTrue(st.paused)
        self.assertEqual(st.clock(20.0), 2.0)          # frozen while paused
        st = handle(" ", st, 20.0)
        self.assertFalse(st.paused)
        self.assertEqual(st.clock(21.0), 3.0)          # continues from 2.0, pause time skipped

    def test_replay_resets_clock(self):
        st = handle("r", State(t0=0.0), 5.0)
        self.assertEqual(st.clock(5.0), 0.0)
        self.assertEqual(st.clock(6.5), 1.5)

    def test_replay_while_paused_stays_paused_at_start(self):
        st = handle(" ", State(t0=0.0), 3.0)
        st = handle("r", st, 7.0)
        self.assertTrue(st.paused)
        self.assertEqual(st.clock(9.0), 0.0)

    def test_log_toggle(self):
        st = handle("l", State(), 0.0)
        self.assertTrue(st.log)
        self.assertFalse(handle("l", st, 0.0).log)

    def test_quit(self):
        self.assertTrue(handle("q", State(), 0.0).quit)

    def test_unknown_keys_ignored(self):
        st = State(t0=1.0, x=2)
        for k in ("x", "h", "j", "k", "\n", "Q"):
            self.assertIs(handle(k, st, 5.0, 10, 10), st)

    def test_pan_moves_and_clamps(self):
        st = handle("right", State(), 0.0, 10, 3)
        self.assertEqual((st.x, st.y), (PAN_X, 0))
        for _ in range(10):
            st = handle("right", st, 0.0, 10, 3)
            st = handle("down", st, 0.0, 10, 3)
        self.assertEqual((st.x, st.y), (10, 3))         # never beyond the canvas
        for _ in range(10):
            st = handle("left", st, 0.0, 10, 3)
            st = handle("up", st, 0.0, 10, 3)
        self.assertEqual((st.x, st.y), (0, 0))

    def test_pan_when_fully_in_view(self):
        st = handle("right", State(), 0.0, 0, 0)
        st = handle("down", st, 0.0, 0, 0)
        self.assertEqual((st.x, st.y), (0, 0))

    def test_parse_arrows_and_chars(self):
        self.assertEqual(parse(b"\x1b[A\x1b[B\x1b[C\x1b[D"), ["up", "down", "right", "left"])
        self.assertEqual(parse(b"\x1bOC q"), ["right", " ", "q"])
        self.assertEqual(parse(b"\x1b[1;5Cr\x1b[5~l"), ["right", "r", "l"])   # modified arrow, PgUp dropped


class Pan(unittest.TestCase):
    def wide(self):
        c = Canvas(30, 10)
        for x in range(30):
            c.put(x, 0, chr(ord("a") + x % 26))
        return c

    def marks(self, c):
        rows = [r.ljust(c.w) for r in c.to_text().split("\n")]
        mid = rows[c.h // 2]
        return (mid.startswith("[+]"), mid.endswith("[+]"),
                "[+]" in rows[0], "[+]" in rows[-1])

    def test_edges_marked_only_where_hidden(self):
        self.assertEqual(self.marks(fit(self.wide(), 10, False, 0, 0, 4)), (False, True, False, True))
        self.assertEqual(self.marks(fit(self.wide(), 10, False, 20, 6, 4)), (True, False, True, False))
        self.assertEqual(self.marks(fit(self.wide(), 10, False, 8, 3, 4)), (True, True, True, True))

    def test_fully_in_view_has_no_marks(self):
        c = fit(self.wide(), 40, False, 0, 0, 20)
        self.assertNotIn("[+]", c.to_text())
        self.assertEqual((c.w, c.h), (30, 10))

    def test_offset_never_beyond_canvas(self):
        c = fit(self.wide(), 10, False, 99, 99, 4)
        self.assertEqual((c.w, c.h), (10, 4))
        self.assertEqual(c.to_text(), fit(self.wide(), 10, False, 20, 6, 4).to_text())   # clamped to max


if __name__ == "__main__":
    unittest.main()
