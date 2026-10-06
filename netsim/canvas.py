# netsim/canvas.py
"""Cell grid. Lines are stored as direction bitmasks so crossings merge into junctions."""
N, E, S, W = 1, 2, 4, 8
OPP = {N: S, E: W, S: N, W: E}
UNI = {0: " ", N: "│", S: "│", N | S: "│", E: "─", W: "─", E | W: "─",
       E | S: "┌", S | W: "┐", N | E: "└", N | W: "┘", N | E | S: "├", N | S | W: "┤",
       E | S | W: "┬", N | E | W: "┴", N | E | S | W: "┼"}


def _ascii(mask):
    if mask in (E, W, E | W):
        return "-"
    if mask in (N, S, N | S):
        return "|"
    return "+" if mask else " "


class Canvas:
    def __init__(self, w, h, ascii=False):
        self.w, self.h, self.ascii = w, h, ascii
        self.mask = [[0] * w for _ in range(h)]
        self.char = [[None] * w for _ in range(h)]
        self.style = [[""] * w for _ in range(h)]

    def _ok(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def put(self, x, y, ch, style=""):
        """put(x, y, ch, style) -- place a character (overrides lines)."""
        if self._ok(x, y):
            self.char[y][x], self.style[y][x] = ch, style

    def text(self, x, y, s, style=""):
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, style)

    def _bits(self, x, y, bits, style):
        if self._ok(x, y):
            self.mask[y][x] |= bits
            if style or not self.style[y][x]:
                self.style[y][x] = style

    def hline(self, x1, x2, y, style=""):
        """hline(x1, x2, y, style) -- horizontal line, merging junctions."""
        x1, x2 = sorted((x1, x2))
        for x in range(x1, x2 + 1):
            self._bits(x, y, (E if x < x2 else 0) | (W if x > x1 else 0), style)

    def vline(self, x, y1, y2, style=""):
        """vline(x, y1, y2, style) -- vertical line, merging junctions."""
        y1, y2 = sorted((y1, y2))
        for y in range(y1, y2 + 1):
            self._bits(x, y, (S if y < y2 else 0) | (N if y > y1 else 0), style)

    def path(self, cells, style=""):
        """path(cells, style) -- polyline through orthogonally adjacent cells, merging junctions."""
        for (x1, y1), (x2, y2) in zip(cells, cells[1:]):
            d = E if x2 > x1 else W if x2 < x1 else S if y2 > y1 else N
            self._bits(x1, y1, d, style)
            self._bits(x2, y2, OPP[d], style)

    def clip(self, w):
        """clip(w) -- drop columns at and right of w, in place."""
        self.w = min(self.w, w)
        for grid in (self.mask, self.char, self.style):
            for row in grid:
                del row[self.w:]

    def box(self, rect, title=None, style="", fill=False):
        """box(rect, title=None) -- bordered rectangle; fill=True clears what is inside."""
        x, y, w, h = rect
        if fill:
            for yy in range(y + 1, y + h - 1):
                for xx in range(x + 1, x + w - 1):
                    if self._ok(xx, yy):
                        self.mask[yy][xx], self.char[yy][xx], self.style[yy][xx] = 0, None, ""
        self.hline(x, x + w - 1, y, style)
        self.hline(x, x + w - 1, y + h - 1, style)
        self.vline(x, y, y + h - 1, style)
        self.vline(x + w - 1, y, y + h - 1, style)
        if title:
            self.text(x + 2, y, f" {title[:max(0, w - 6)]} ", style)

    def glyph(self, x, y):
        ch = self.char[y][x]
        if ch is not None:
            return ch
        m = self.mask[y][x]
        return _ascii(m) if self.ascii else UNI[m]

    def to_text(self):
        """to_text() -- plain string, trailing spaces stripped."""
        return "\n".join("".join(self.glyph(x, y) for x in range(self.w)).rstrip() for y in range(self.h))

    def to_rich(self):
        """to_rich() -- rich.text.Text with per-cell styles."""
        from rich.text import Text
        out = Text()
        for y in range(self.h):
            for x in range(self.w):
                out.append(self.glyph(x, y), self.style[y][x] or None)
            if y < self.h - 1:
                out.append("\n")
        return out
