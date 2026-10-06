# netsim/watch.py
"""Exec a topo file in staged try blocks and show the frame, live or once."""
import copy
import os
import shutil
import signal
import sys
import time

from . import log
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


def watch(path, ascii=False):
    """watch(path) -- live render at 20 fps; re-exec when the file's mtime changes and
    replay the packet animation only if the recorded sends changed."""
    from rich.console import Group
    from rich.live import Live
    from rich.text import Text

    from .anim import Timeline

    frame, last, good, resized = None, object(), False, []
    sends, t0, end, playing, fitted = None, 0.0, 0.0, False, None
    winch = hasattr(signal, "SIGWINCH")                # Unix only: recompute on terminal resize
    old = signal.signal(signal.SIGWINCH, lambda *_: resized.append(1)) if winch else None
    try:
        with Live(screen=True, auto_refresh=False) as live:
            while True:
                tick = time.monotonic()
                m, dirty = _mtime(path), False
                if m != last:
                    last, dirty, fitted = m, True, None     # build clears the tool log, so T_FIT may log again
                    new = build(path, ascii)
                    frame, good = new or frame, new is not None
                    if good and model.events != sends:
                        sends, t0, end = copy.deepcopy(model.events), tick, Timeline.build(model.events).end
                if resized:
                    resized.clear()
                    dirty = True
                    if good:                                # same model, fresh layout and render
                        try:
                            frame = render(model, ascii, layout(model))
                        except Exception as e:
                            log.tool.add("T_RENDER", "render", f"Error: {type(e).__name__}: {e}")
                anim = good and tick - t0 < end
                if anim or playing:                         # one more redraw after the end clears the dots
                    try:
                        frame = render(model, ascii, layout(model), now=tick - t0 if anim else None)
                    except Exception as e:
                        log.tool.add("T_RENDER", "render", f"Error: {type(e).__name__}: {e}")
                        end, anim = 0.0, False              # stop the replay instead of logging every tick
                    dirty, playing = True, anim
                if dirty:
                    cols, shown = shutil.get_terminal_size().columns, None
                    if frame:
                        shown = fit(copy.deepcopy(frame), cols, warn=(frame.w, cols) != fitted)
                        fitted = (frame.w, cols)
                    parts = [shown.to_rich() if shown else Text("(no frame yet)", "dim"), Text(""),
                             Text(status(model, ascii) + f" | {os.path.basename(path)} | Ctrl-C quits", "dim")]
                    parts += [Text(str(e), "red") for e in log.tool.entries]
                    live.update(Group(*parts), refresh=True)
                time.sleep(max(0.0, 0.05 - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        if winch:
            signal.signal(signal.SIGWINCH, old)
