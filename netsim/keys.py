"""Watch-mode keys: parse raw stdin bytes, then a pure key + state -> state handler."""
from dataclasses import dataclass, replace

LOG_LINES = 8       # net-log lines in the bottom strip
PAN_X, PAN_Y = 4, 2  # cells per arrow press
ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}


@dataclass(frozen=True)
class State:
    t0: float = 0.0          # animation start (monotonic)
    paused: bool = False
    pause_at: float = 0.0    # monotonic time the pause began
    log: bool = False        # bottom log strip shown
    x: int = 0               # pan offset into the canvas
    y: int = 0
    quit: bool = False

    def clock(self, now):
        """clock(now) -- animation time; frozen while paused."""
        return (self.pause_at if self.paused else now) - self.t0

    def restart(self, now):
        """restart(now) -- animation time back to 0, keeping the pause state."""
        return replace(self, t0=now, pause_at=now)


def parse(data):
    """parse(data) -- list of keys from raw bytes: single characters, or 'up'/'down'/'left'/'right'.
    Unknown escape sequences are dropped."""
    s, out, i = data.decode("utf-8", "replace"), [], 0
    while i < len(s):
        if s[i] == "\x1b" and i + 2 < len(s) and s[i + 1] in "[O":
            j = i + 2
            while j < len(s) and not ("@" <= s[j] <= "~"):   # skip parameter bytes, e.g. "1;5"
                j += 1
            if j < len(s) and s[j] in ARROWS:
                out.append(ARROWS[s[j]])
            i = j + 1
        else:
            out.append(s[i])
            i += 1
    return out


def clamp(st, max_x, max_y):
    """clamp(st, max_x, max_y) -- keep the pan offset inside 0..max."""
    x, y = max(0, min(st.x, max_x)), max(0, min(st.y, max_y))
    return st if (x, y) == (st.x, st.y) else replace(st, x=x, y=y)


def handle(key, st, now, max_x=0, max_y=0):
    """handle(key, st, now, max_x, max_y) -- new State after one key. Unknown keys return st unchanged."""
    if key == "q":
        return replace(st, quit=True)
    if key == " ":
        if st.paused:
            return replace(st, paused=False, t0=st.t0 + now - st.pause_at)
        return replace(st, paused=True, pause_at=now)
    if key == "r":
        return st.restart(now)
    if key == "l":
        return replace(st, log=not st.log)
    dx, dy = {"left": (-PAN_X, 0), "right": (PAN_X, 0), "up": (0, -PAN_Y), "down": (0, PAN_Y)}.get(key, (0, 0))
    if dx or dy:
        return clamp(replace(st, x=st.x + dx, y=st.y + dy), max_x, max_y)
    return st
