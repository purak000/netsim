# netsim/watch.py
"""Exec a topo file in staged try blocks and show the frame, live or once."""
import copy
import os
import shutil
import signal
import sys
import time

from . import keys, log
from .dsl import NetsimError, model, namespace
from .layout import layout
from .render import fit, render, status
from .validate import validate


def _line(exc, path):
    tb, line = exc.__traceback__, None
    while tb:
        if tb.tb_frame.f_code.co_filename == path:
            line = tb.tb_lineno
        tb = tb.tb_next
    return f"line {line}" if line else path


def build(path, ascii=False):
    """build(path) -- reset, compile, exec, layout, render. Canvas, or None on error."""
    path = os.path.abspath(path)
    model.reset(); log.net.clear(); log.tool.clear()
    try:
        with open(path) as f:
            src = f.read()
    except OSError as e:
        log.tool.add("T_IO", path, f"Error: cannot read file ({e.strerror})")
        return None
    try:
        code = compile(src, path, "exec")
    except SyntaxError as e:
        log.tool.add("T_SYNTAX", f"line {e.lineno}", f"Error: {e.msg}")
        return None
    try:
        exec(code, {"__name__": "__netsim__", "__file__": path, **namespace()})
    except NetsimError as e:
        log.tool.add(e.code, _line(e, path), e.msg)
        return None
    except (Exception, SystemExit) as e:
        log.tool.add("T_EXC", _line(e, path), f"Error: {type(e).__name__}: {e}")
        return None
    try:
        validate(model)
    except Exception as e:
        log.tool.add("T_ERROR", "validate", f"Error: {type(e).__name__}: {e}")
    try:
        rects = layout(model)
    except Exception as e:
        log.tool.add("T_LAYOUT", "layout", f"Error: {type(e).__name__}: {e}")
        return None
    try:
        return render(model, ascii, rects)
    except Exception as e:
        log.tool.add("T_RENDER", "render", f"Error: {type(e).__name__}: {e}")
        return None


def step(path, prev=None, ascii=False):
    """step(path, prev) -- rebuild; keep prev (last good frame) if any stage fails."""
    return build(path, ascii) or prev


def run_once(path, ascii=False):
    """run_once(path) -- print one plain frame to stdout; errors go to stderr. Exit code."""
    canvas = build(path, ascii)
    if canvas and sys.stdout.isatty():
        canvas = fit(canvas, shutil.get_terminal_size().columns)
    if canvas:
        print(canvas.to_text())
    print(status(model, ascii))
    for e in log.tool.entries:
        print(e, file=sys.stderr)
    return 0 if canvas else 1


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def _keyboard():
    """_keyboard() -- (fd, saved termios) with stdin in cbreak mode, or (None, None) if stdin is not a TTY."""
    if not sys.stdin.isatty():
        return None, None
    import termios
    import tty
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return fd, saved


def _restore(fd, saved):
    if fd is not None:
        import termios
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _read_keys(fd):
    """_read_keys(fd) -- keys waiting on fd, without blocking."""
    import select
    data = b""
    while fd is not None and select.select([fd], [], [], 0)[0]:
        chunk = os.read(fd, 64)
        if not chunk:
            break
        data += chunk
    return keys.parse(data) if data else []


def _stop(*_):
    raise KeyboardInterrupt


def watch(path, ascii=False):
    """watch(path) -- live render at 20 fps; re-exec when the file's mtime changes and
    replay the packet animation only if the recorded sends changed.
    Keys: q quit, space pause/resume, r replay, l log strip, arrows pan."""
    from rich.console import Group
    from rich.live import Live
    from rich.text import Text

    from .anim import Timeline

    frame, last, good, resized = None, object(), False, []
    sends, end, playing, fitted, st = None, 0.0, False, None, keys.State()
    winch = hasattr(signal, "SIGWINCH")                # Unix only: recompute on terminal resize
    old = signal.signal(signal.SIGWINCH, lambda *_: resized.append(1)) if winch else None
    old_term = signal.signal(signal.SIGTERM, _stop)   # SIGTERM unwinds like Ctrl-C so the terminal is restored
    fd = saved = None

    def view(term):
        """view(term) -- (log strip, canvas rows, max pan x, max pan y) for the current st and frame."""
        strip = list(log.net.entries)[-keys.LOG_LINES:] if st.log else []
        rows = max(1, term.lines - 2 - len(log.tool.entries) - (len(strip) + 1 if st.log else 0))
        return (strip, rows, max(0, frame.w - term.columns) if frame else 0,
                max(0, frame.h - rows) if frame else 0)

    try:
        fd, saved = _keyboard()
        with Live(screen=True, auto_refresh=False) as live:
            while True:
                tick = time.monotonic()
                m, dirty = _mtime(path), False
                if m != last:
                    last, dirty, fitted = m, True, None     # build clears the tool log, so T_FIT may log again
                    new = build(path, ascii)
                    frame, good = new or frame, new is not None
                    if good and model.events != sends:
                        sends, end = copy.deepcopy(model.events), Timeline.build(model.events).end
                        st = st.restart(tick)
                if resized:
                    resized.clear()
                    dirty = True
                    if good:                                # same model, fresh layout and render
                        try:
                            frame = render(model, ascii, layout(model))
                        except Exception as e:
                            log.tool.add("T_RENDER", "render", f"Error: {type(e).__name__}: {e}")
                term = shutil.get_terminal_size()
                strip, rows, max_x, max_y = view(term)
                for k in _read_keys(fd):
                    new_st = keys.handle(k, st, tick, max_x, max_y)
                    dirty = dirty or new_st != st
                    st = new_st
                if st.quit:
                    break
                strip, rows, max_x, max_y = view(term)     # keys may have toggled the log strip
                st = keys.clamp(st, max_x, max_y)          # frame or terminal may have shrunk
                now = st.clock(tick)
                anim = good and now < end
                if (anim and (not st.paused or dirty)) or (playing and not anim):
                    try:                                    # one more redraw after the end clears the dots
                        frame = render(model, ascii, layout(model), now=now if anim else None)
                    except Exception as e:
                        log.tool.add("T_RENDER", "render", f"Error: {type(e).__name__}: {e}")
                        end, anim = 0.0, False              # stop the replay instead of logging every tick
                    dirty, playing = True, anim
                if dirty:
                    shown = None
                    if frame:
                        shown = fit(copy.deepcopy(frame), term.columns, warn=(frame.w, term.columns) != fitted,
                                    x=st.x, y=st.y, rows=rows)
                        fitted = (frame.w, term.columns)
                    hint = "paused | " if st.paused else ""
                    parts = [shown.to_rich() if shown else Text("(no frame yet)", "dim"), Text(""),
                             Text(status(model, ascii) + f" | {os.path.basename(path)} | {hint}"
                                  "q quit, space pause, r replay, l log, arrows pan", "dim")]
                    parts += [Text(str(e), "red") for e in log.tool.entries]
                    if st.log:
                        parts += [Text("-- net log --", "dim")] + [Text(str(e)) for e in strip]
                    live.update(Group(*parts), refresh=True)
                time.sleep(max(0.0, 0.05 - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        _restore(fd, saved)
        signal.signal(signal.SIGTERM, old_term)
        if winch:
            signal.signal(signal.SIGWINCH, old)
