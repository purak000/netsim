# netsim/docs.py
"""DSL help and roff man page, generated from docstrings and CODES."""
import difflib
import inspect

from . import log

CATEGORIES = {}                     # function name -> category
ORDER = ("devices", "wiring", "state", "traffic")
COMMANDS = {
    "init [file]": "write a sample topology (default topo.py)",
    "watch file": "live render, re-exec on save (Ctrl-C quits)",
    "run file": "print one plain frame and the status bar to stdout",
    "logs [file] [--net|--tool] [--level E|W|I] [--last N]": "print the log files; with file, re-run it first",
    "help [name]": "DSL help; names: a function, codes, dots",
    "man [--install]": "print this man page as roff, or install it",
}
DOTS = [("●", "*", "power on (green), bottom-left"), ("○", "o", "power off (red), bottom-left"),
        ("●", ".", "activity, bottom-right (dim when idle)"), ("×", "x", "on a link: link is down")]


def category(cat):
    """category(cat) -- decorator that files a DSL function under a help category."""
    def deco(fn):
        CATEGORIES[fn.__name__] = cat
        return fn
    return deco


def _functions():
    from .dsl import namespace
    return {k: v for k, v in namespace().items() if inspect.isfunction(v)}


def _summary(fn):
    return inspect.getdoc(fn).splitlines()[0]


def help_text(topic=None):
    """help_text(topic=None) -- the text info() prints, or None if topic is unknown."""
    fns = _functions()
    if topic is None:
        out = []
        for cat in ORDER:
            out.append(f"{cat}:")
            out += [f"  {_summary(f)}" for k, f in fns.items() if CATEGORIES.get(k) == cat]
        out.append('more: info(name), info("codes"), info("dots")')
        return "\n".join(out)
    name = getattr(topic, "__name__", topic)
    if name == "codes":
        return "\n".join(f"{c:<13} {lvl}  {text}" for c, (lvl, text) in log.CODES.items())
    if name == "dots":
        return "\n".join(f"{u} ({a})  {text}" for u, a, text in DOTS)
    if name in fns:
        return inspect.getdoc(fns[name])
    return None


def info(topic=None):
    """info(topic=None) -- print DSL help: overview, one function, "codes" or "dots".
    Unknown names suggest close matches and log T_UNKNOWN."""
    text = help_text(topic)
    if text is None:
        name = str(getattr(topic, "__name__", topic))
        close = difflib.get_close_matches(name, list(_functions()) + ["codes", "dots"])
        hint = f"; did you mean {', '.join(close)}?" if close else ""
        msg = f"Error: no help for '{name}'{hint}"
        log.tool.add("T_UNKNOWN", "info", msg)
        text = msg
    print(text)


def _esc(s):
    s = s.replace("\\", "\\e").replace("-", "\\-")
    return "\n".join("\\&" + l if l[:1] in (".", "'") else l for l in s.splitlines())


def man_page():
    """man_page() -- roff source for netsim(1)."""
    fns = _functions()
    r = ['.TH NETSIM 1 "" "netsim 0.1" "User Commands"',
         ".SH NAME", "netsim \\- terminal network topology visualizer",
         ".SH SYNOPSIS"]
    r += [f".B netsim\n{_esc(c)}\n.br" for c in COMMANDS]
    r += [".SH DESCRIPTION",
          "netsim draws a network topology described in a plain Python file and re-renders it on save. "
          "Topology files are trusted Python code: they are executed with the DSL functions below in scope. "
          "Global option \\fB\\-\\-ascii\\fR uses ASCII instead of box drawing; NO_COLOR disables color.",
          ".SH COMMANDS"]
    r += [f".TP\n.B {_esc(c)}\n{_esc(d)}" for c, d in COMMANDS.items()]
    r.append(".SH DSL FUNCTIONS")
    for cat in ORDER + (None,):
        names = [k for k, f in fns.items() if CATEGORIES.get(k) == cat]
        if names:
            r.append(f".SS {cat or 'help'}")
        for k in names:
            head, *rest = inspect.getdoc(fns[k]).splitlines()
            r.append(f".TP\n.B {_esc(head)}" + ("\n" + _esc("\n".join(rest)) if rest else ""))
    r.append(".SH DOT LEGEND")
    r += [f".TP\n{u} ({a})\n{_esc(t)}" for u, a, t in DOTS]
    r.append(".SH ERROR CODES")
    r += [f".TP\n.B {_esc(c)} ({lvl})\n{_esc(t)}" for c, (lvl, t) in log.CODES.items()]
    r += [".SH FILES",
          ".TP\n~/.netsim/tool.log\ntool errors, appended across runs",
          ".TP\n~/.netsim/net.log\nnetwork log of the last reload, overwritten each reload",
          ".TP\n~/.local/share/man/man1/netsim.1\nthis page, written by \\fBnetsim man \\-\\-install\\fR",
          ".SH EXAMPLES",
          ".nf", "netsim init topo.py", "netsim watch topo.py", "netsim logs \\-\\-net \\-\\-level E",
          "netsim help join", ".fi", ""]
    return "\n".join(r)
