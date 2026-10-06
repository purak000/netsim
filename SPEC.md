# netsim SPEC (v0.1)

**Status:** steps 1-4 built (see section 14). Next: step 5.

Terminal network topology visualizer with packet animation. Python, Linux/macOS only.
Topology files are **trusted Python code**. Do not watch files you did not write.

**Principle:** smallest useful version first, with clean interfaces so it can grow into a simulator.
**Rule:** the model never knows how it is displayed.

## 1. Scope

- v0.1 = visualizer + hop-by-hop packet animation + logs + help/man.
- NOT in v0.1: ARP, MAC learning, routing tables, DHCP, NAT, VLANs, TCP/UDP.
- Hooks for later: `Device.on_packet(pkt, in_iface) -> list[(iface, pkt)]`, a no-op in v0.1 (flood or BFS path).

## 2. Usage

```
netsim init [file]        scaffold topo.py
netsim watch topo.py      live render, re-exec on save (use with LazyVim + tmux split)
netsim run topo.py        one frame to stdout (--json for frame + logs)
netsim logs topo.py       tail logs (--net|--tool, --level E)
netsim validate topo.py   checks only
netsim help [cmd]         DSL help
netsim man [--install]    roff man page
netsim export topo.py     --txt|--mermaid|--svg (later)
netsim watch ... --record / netsim replay rec.json   (later)
```

Flags: `--ascii`, `NO_COLOR` respected, `--net-log FILE`.
Optional built-in REPL (two panes) is built last, only if still wanted.

## 3. DSL (plain Python, exec'd in an injected namespace, no parser)

```python
from netsim import *            # makes the file valid standalone Python for LSP

pc1 = host("PC1"); sw1 = switch("SW1"); r1 = router("R1")
d1  = dns("DNS1");  c1 = cloud("Internet")
join(pc1, sw1, r1)                          # chain
join(sw1, r1, latency=10, loss=0.01)        # link props
star(sw1, pc1, pc2, pc3)
lan = group("LAN1", pc1, sw1, kind="lan", gw=r1, collapsed=False)
join(lan, wan)                              # groups resolve to gateway
power(r1, "off")      label(pc1, "10.0.0.2")      ip(pc1, "10.0.0.2/24")
down(sw1, r1)         send(pc1, d1)               at(2, power, r1, "off")
info()  info(join)    # DSL help (never shadow builtin help)
```

Link props: `bandwidth`, `latency` (ms), `loss` (0..1), `up`.
Rules: group-to-group `join` resolves to a gateway (`gw`, else first router, else first member; warn `N_GW_MISSING`). The model only links nodes.
Duplicate names raise `T_NAME`. Every function has a docstring.

## 4. Architecture

```
netsim/
  model.py     Node, Group, Link, Model, reset()
  engine.py    BFS path (visited set), Packet(src,dst,ttl,proto,payload), TTL guard, send diagnostics, events
  dsl.py       constructors, join/star/send/power/..., namespace builder, NetsimError
  layout.py    model -> {id: Rect}; cached on structure only (not power/send state)
  canvas.py    cell grid, junction merge, ascii charset
  render.py    groups, links, nodes, dots, status bar
  anim.py      timeline of (t, node, kind); dot-state lookup; latency drives timing
  log.py       Entry, Log (ring buffer, file sink), CODES table
  validate.py  post-exec checks
  docs.py      help() text + roff man generator from docstrings and CODES
  watch.py     poll mtime, exec in subprocess with timeout, key input, Live loop
  cli.py       argument handling and subcommands
  __init__.py  exports DSL names
pyproject.toml  package name `netsim-tui` (`netsim` is taken on PyPI); console script and import stay `netsim`; pip install -e . / pipx install .
```

Data flow: `topo.py -> exec -> Model -> Layout(cached) -> Canvas -> ANSI frame`, with `Engine events -> Timeline -> dot overlay per tick`.
Future shape: `Topology -> Model -> Event/Packet Engine -> Device behavior -> Renderer`. A GUI renderer can replace the terminal one.

## 5. Rendering

- Node box fixed 10x4 (names cut to 8 chars, labels to 6), name colored by kind (router cyan, switch magenta, dns yellow, host white, cloud blue; one theme dict).
- Dots: left = power, `●` on (green) / `○` off (red). Right = activity, dim idle, yellow when a packet arrives, **red on drop**. Symbols carry meaning, color only supplements.
- Group box with embedded title `┌─ LAN1 ───┐`; nested groups drawn outer to inner; `collapsed=True` draws one box.
- Links: neighbours get a straight line; otherwise orthogonal paths plus junction table (`─`+`│`=`┼`). A link that would cross a box goes down, across and back up below the row. Down links are drawn with `x`. No general auto-router.
- Layout: BFS layers from the gateway per group (a layer is a column); top-level groups left to right, 6 to 8 cell gap; declaration order for stability (no hashes). Visited set for cycles.
- Auto-fit: wider than terminal gives pan plus `T_FIT` warning. Recompute on `SIGWINCH`.
- Status bar: `● on  ○ off  ● traffic | 5n 4l | NET 1E 2W | TOOL 0E | OK`.
- Only box-drawing glyphs and `●○` (no emoji, avoids width bugs).

## 6. Animation and input

- `send` computes the path and schedules hop i at `t0 + sum(latency)`; the dot lights for about 0.3s. Loss is drawn red at the drop point.
- On reload, replay only if the `send` lines changed (default no flicker).
- One loop: `time.monotonic()`, non-blocking stdin, no threads, 20 fps.
- Keys: `q` quit, `space` pause/resume, `r` replay, `l` toggle log strip, arrows or `hjkl` pan.
  (`l` is toggle-log, so pan-right is arrow only. Pick one in code.)

## 7. Logging (two channels, one `Entry(t, lvl, code, where, msg)`)

| | Network log | Tool log |
|---|---|---|
| Answers | What happened in the simulated network | What went wrong in netsim or topo file |
| Lifetime | cleared each reload | current-run cleared on reload, also appended to `~/.netsim/tool.log` |

Line format: `t=1.25 E N_NODE_OFF r1 send pc1>dns1 dropped at r1 (off)`.

**Network codes**

| Code | Lvl | Meaning |
|---|---|---|
| N_CREATE / N_LINK | I | device or link created |
| N_SEND / N_HOP | I | packet sent / hop traversed |
| N_DELIVER | I | delivered (path, hops) |
| N_LOSS | E | dropped by link loss |
| N_DROP | E | dropped (generic) |
| N_NODE_OFF | E | blocked by powered-off node (report the first one on the path) |
| N_LINK_DOWN | E | link down |
| N_NOPATH | E | no path |
| N_NOROUTE | E | no route (later) |
| N_TTL | E | TTL expired / loop |
| N_DNS_NX | E | DNS lookup failed |
| N_SUBNET | W | subnet mismatch on a link |
| N_ISOLATED | W | node with no links |
| N_GW_MISSING | W | group has no gateway, fallback used |

**Tool codes**

| Code | Lvl | Meaning |
|---|---|---|
| T_SYNTAX | E | compile error |
| T_EXC | E | exception in topo file (line via tb_lineno) |
| T_TIMEOUT | E | exec exceeded limit (subprocess preferred, `signal.alarm` fallback) |
| T_NAME | E | duplicate name |
| T_UNKNOWN | E | unknown or unregistered object |
| T_ARGS | E | bad argument, e.g. loss outside 0..1, bad latency, unsupported kind |
| T_LAYOUT | E | layout stage failed (as built). Auto-fit warning needs its own code, e.g. T_FIT (W), when auto-fit exists |
| T_RENDER | E | renderer crashed, last good frame kept |
| T_IO | E | file missing or unreadable |
| T_ERROR | E | other tool error |

Rules: compile, exec, layout, render each in its own try block so the code says which stage failed.
Tool errors never crash the loop: keep the last good frame, show the count in the status bar.
DSL raises `NetsimError(code, msg)`; unexpected exceptions become `T_EXC`.
Messages are clear: `Error: device 'R1' already exists`, `Error: loss must be between 0 and 1`.

## 8. Validation (`validate.py`, after exec, before animation)

Duplicate names, invalid links or missing endpoints, latency or loss out of range, unsupported kind, isolated nodes, subnet mismatch, missing group gateway.

## 9. Help and man (single source: docstrings)

- Docstring format: line 1 = `signature -- summary`, then details, then `Example:`. Category via small decorator.
- `info()` / `netsim help [cmd]` walk the namespace. `info("codes")`, `info("dots")`, `info("tour")`. Unknown name suggests `difflib.get_close_matches`.
- `netsim man` emits roff: NAME, SYNOPSIS, DESCRIPTION, COMMANDS, DSL FUNCTIONS (generated), DOT LEGEND, ERROR CODES (generated from `CODES`), FILES, EXAMPLES, SEE ALSO. `--install` writes `~/.local/share/man/man1/netsim.1`.
- LazyVim: `K` shows docstrings via LSP hover for free.

## 10. Tests

- Golden frames: `render(model)` as plain text vs stored `.txt` (chain, star, nested groups, off node, group join, cycle).
- Model: BFS skips off nodes, group join resolves to gateway, cycles terminate.
- Net log: send through an off router yields exactly one `N_NODE_OFF` with `where == "r1"`.
- Tool log: duplicate name yields `T_NAME` with the right line; last frame preserved; infinite loop yields `T_TIMEOUT`.
- Docs: every DSL function has a docstring; every code used in source is in `CODES`; `netsim man` starts with `.TH`.

## 11. Build order

1. `model.py`, `dsl.py`, `log.py`, `NetsimError`, `CODES` (headless tests)
2. `canvas.py`, naive single-row `layout.py`, `render.py`, verify with `run`
3. `watch.py` (staged try blocks, subprocess timeout, tool log) -> usable with LazyVim. `cli.py` with `init`/`watch`/`run`, `pyproject.toml`
4. `engine.py` send diagnostics, `validate.py`, net log
5. `netsim logs`, status bar counters, `docs.py` (help then man)
6. Real layout, link routing, collapse, auto-fit, resize
7. `anim.py` (yellow and red dots), keyboard controls, pause
8. `at()`, `ip()`, export, record/replay, optional REPL pane

Steps 1 to 3 are about 350 lines. Target total about 1000 lines, `rich` as the only dependency.

## 12. Roadmap (after the visualizer is stable)

1. Ethernet frames, MAC addresses, switch MAC learning
2. IP addresses, ARP, routing tables, ICMP
3. DHCP, NAT, VLANs
4. TCP/UDP, ports, application traffic

## 13. Housekeeping

Check the `netsim` name on PyPI before committing to it. Provide `README.md` (what it is, install, quick start, DSL, keys, limitations, roadmap) and `LICENSE`. Document that topo files are trusted code.

## 14. Build status and as-built deviations

**Done (steps 1-4):** model, dsl, log, canvas, naive layout, render, watch, cli, pyproject; engine.py (BFS path, send diagnostics), validate.py (N_ISOLATED, N_GW_MISSING), tests/test_errors.py (9 tests passing). `pip install -e .`, `init`, `run`, `watch` work.
Tested: T_NAME, T_ARGS, T_SYNTAX, T_IO, T_EXC (line number), T_UNKNOWN, T_LAYOUT / T_RENDER keep the last good frame, 3-node cycle (no link through a box), send delivered / N_NODE_OFF at r1 / N_NOPATH / N_LINK_DOWN, nested groups, watch re-render on save, Ctrl-C.
**Added:** step 5 (`netsim logs`, net.log sink, docs.py `info()` / `help` / `man`) and `down(a, b)` / `up(a, b)` in the DSL (state, log N_LINK); 17 tests passing.
**Not yet tested:** watch in a real terminal (tmux).

**Deviations from the plan above:**
- Layout is naive: one row in declaration order, no BFS layers, no collapse, no auto-fit.
- Group members follow the order passed to `group()`.
- Model resets in place, so `from netsim import *` in a topo file shares the same model.
- `send()` runs when called (no timeline yet), so `power()` / `down()` must come before it to affect it.
- A failed send logs only the error code (N_NODE_OFF, N_LINK_DOWN, N_NOPATH, N_TTL), not N_SEND.
- N_GW_MISSING is logged only by validate.py, for groups with no `gw` and no router.
- validate.py checks N_ISOLATED and N_GW_MISSING only; subnet and range checks are not in it yet.
- No exec timeout yet (`T_TIMEOUT` pending), no animation, keys, export.

**Next:** step 5 (`netsim logs`, status bar counters, docs.py: help then man). Keep animation and layout upgrades in separate sessions.
