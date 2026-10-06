# netsim/anim.py
"""Timeline of (t, node, kind) from recorded send events; dot-state lookup per tick."""
from dataclasses import dataclass

DOT = 0.3           # seconds a dot stays lit
STEP = 0.25         # seconds per hop on a 0 ms link


@dataclass
class Timeline:
    entries: list   # (t, node, kind), kind "hop" (yellow) or "drop" (red)
    end: float

    @classmethod
    def build(cls, events, t0=0.0):
        """build(events, t0) -- sends play one after another; hop i lights at t0 + sum(earlier hop latency).
        The last node of a dropped send lights red instead of yellow."""
        entries, t = [], t0
        for ev in events:
            for i, n in enumerate(ev.path):
                last = i == len(ev.path) - 1
                entries.append((t, n, "drop" if last and ev.outcome == "dropped" else "hop"))
                if not last:
                    t += ev.latency[i] / 1000 if ev.latency[i] > 0 else STEP
            t += DOT
        return cls(entries, t)

    def state(self, now):
        """state(now) -- {node: kind} lit at time now; a drop wins over a hop."""
        out = {}
        for t, n, kind in self.entries:
            if t <= now < t + DOT and out.get(n) != "drop":
                out[n] = kind
        return out
