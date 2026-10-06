# netsim/cli.py
"""netsim command line: init, watch, run, logs, help, man."""
import argparse
import os
import sys

SAMPLE = '''from netsim import *

pc1 = host("PC1")
pc2 = host("PC2")
sw1 = switch("SW1")
r1 = router("R1")

join(pc1, sw1, r1)
join(pc2, sw1)
lan = group("LAN1", pc1, pc2, sw1)
label(pc1, "10.0.1")
'''


def man(install=False):
    from .docs import man_page
    page = man_page()
    if not install:
        print(page, end="")
        return 0
    path = os.path.expanduser("~/.local/share/man/man1/netsim.1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(page)
    print(f"wrote {path}; try: man netsim")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="netsim", description="Terminal network topology visualizer")
    p.add_argument("--ascii", action="store_true", help="ASCII charset instead of box drawing")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write a sample topology").add_argument("file", nargs="?", default="topo.py")
    sub.add_parser("watch", help="live render, re-exec on save").add_argument("file")
    sub.add_parser("run", help="print one frame to stdout").add_argument("file")
    lg = sub.add_parser("logs", help="print the log files, filtered")
    lg.add_argument("file", nargs="?", help="topo file to re-run first (refreshes net.log)")
    ch = lg.add_mutually_exclusive_group()
    ch.add_argument("--net", action="store_true")
    ch.add_argument("--tool", action="store_true")
    lg.add_argument("--level", choices="IWE", default="I", help="minimum level (I < W < E)")
    lg.add_argument("--last", type=int, metavar="N")
    sub.add_parser("help", help="DSL help").add_argument("name", nargs="?")
    sub.add_parser("man", help="roff man page").add_argument("--install", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "init":
        if os.path.exists(a.file):
            sys.exit(f"Error: {a.file} already exists")
        with open(a.file, "w") as f:
            f.write(SAMPLE)
        print(f"wrote {a.file}; try: netsim watch {a.file}")
        return 0
    if a.cmd == "help":
        from .docs import info
        info(a.name)
        return 0
    if a.cmd == "man":
        return man(a.install)
    from .watch import build, run_once, watch
    if a.cmd == "logs":
        from . import log
        if a.file:
            build(a.file, a.ascii)
        sinks = [log.net.sink] * (not a.tool) + [log.tool.sink] * (not a.net)
        lines = [ln for s in sinks for ln in log.read_lines(s, a.level)]
        lines = lines[-a.last:] if a.last else lines
        if lines:
            print("\n".join(lines))
        return 0
    if a.cmd == "run":
        return run_once(a.file, a.ascii)
    watch(a.file, a.ascii)
    return 0


if __name__ == "__main__":
    sys.exit(main())
