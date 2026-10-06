# netsim/cli.py
"""netsim command line: init, watch, run."""
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


def main(argv=None):
    p = argparse.ArgumentParser(prog="netsim", description="Terminal network topology visualizer")
    p.add_argument("--ascii", action="store_true", help="ASCII charset instead of box drawing")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write a sample topology").add_argument("file", nargs="?", default="topo.py")
    sub.add_parser("watch", help="live render, re-exec on save").add_argument("file")
    sub.add_parser("run", help="print one frame to stdout").add_argument("file")
    a = p.parse_args(argv)

    if a.cmd == "init":
        if os.path.exists(a.file):
            sys.exit(f"Error: {a.file} already exists")
        with open(a.file, "w") as f:
            f.write(SAMPLE)
        print(f"wrote {a.file}; try: netsim watch {a.file}")
        return 0
    from .watch import run_once, watch
    if a.cmd == "run":
        return run_once(a.file, a.ascii)
    watch(a.file, a.ascii)
    return 0


if __name__ == "__main__":
    sys.exit(main())
