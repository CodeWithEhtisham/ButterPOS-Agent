#!/usr/bin/env python3
"""
Realistic activity bot for Wayland (COSMIC / Pop!_OS).

Uses the Linux kernel uinput interface (via evdev) to inject REAL mouse
and keyboard events that the Wayland compositor honours — pyautogui can't
do this because it talks Xlib which is ignored on native Wayland.

Usage:
    python3 activity_bot.py              # run for 8 hours
    python3 activity_bot.py --hours 4    # run for 4 hours
    python3 activity_bot.py --hours 0    # run forever

Press Ctrl+C at any time to stop.
"""

import argparse
import math
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta

import evdev
from evdev import UInput, AbsInfo, ecodes

# ---------------------------------------------------------------------------
# Monitor layout — auto-detected from cosmic-randr at startup
# ---------------------------------------------------------------------------
MONITORS: list[dict] = []
TOTAL_W, TOTAL_H = 3840, 1080  # fallback


def _detect_monitors():
    """Parse `cosmic-randr list` to get monitor positions and sizes."""
    global MONITORS, TOTAL_W, TOTAL_H
    try:
        out = subprocess.check_output(
            ["cosmic-randr", "list"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception:
        MONITORS.append({"x": 0, "y": 0, "w": 1920, "h": 1080, "name": "default"})
        return

    import re
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)  # strip ANSI colour codes
    blocks = re.split(r"(?=^\S)", out, flags=re.MULTILINE)
    for block in blocks:
        if "(enabled)" not in block:
            continue
        name_m = re.match(r"(\S+)", block)
        pos_m = re.search(r"Position:\s*(\d+)\s*,\s*(\d+)", block)
        mode_m = re.search(r"(\d+)x(\d+)\s.*?\(current\)", block)
        if name_m and pos_m and mode_m:
            MONITORS.append({
                "name": name_m.group(1).strip(),
                "x": int(pos_m.group(1)),
                "y": int(pos_m.group(2)),
                "w": int(mode_m.group(1)),
                "h": int(mode_m.group(2)),
            })

    if not MONITORS:
        MONITORS.append({"x": 0, "y": 0, "w": 1920, "h": 1080, "name": "fallback"})

    max_right = max(m["x"] + m["w"] for m in MONITORS)
    max_bottom = max(m["y"] + m["h"] for m in MONITORS)
    TOTAL_W, TOTAL_H = max_right, max_bottom


# ---------------------------------------------------------------------------
# Virtual input device (kernel uinput)
# ---------------------------------------------------------------------------
_device: UInput | None = None

_KEY_MAP = {
    "a": ecodes.KEY_A, "b": ecodes.KEY_B, "c": ecodes.KEY_C,
    "d": ecodes.KEY_D, "e": ecodes.KEY_E, "f": ecodes.KEY_F,
    "g": ecodes.KEY_G, "h": ecodes.KEY_H, "i": ecodes.KEY_I,
    "j": ecodes.KEY_J, "k": ecodes.KEY_K, "l": ecodes.KEY_L,
    "m": ecodes.KEY_M, "n": ecodes.KEY_N, "o": ecodes.KEY_O,
    "p": ecodes.KEY_P, "q": ecodes.KEY_Q, "r": ecodes.KEY_R,
    "s": ecodes.KEY_S, "t": ecodes.KEY_T, "u": ecodes.KEY_U,
    "v": ecodes.KEY_V, "w": ecodes.KEY_W, "x": ecodes.KEY_X,
    "y": ecodes.KEY_Y, "z": ecodes.KEY_Z,
    " ": ecodes.KEY_SPACE,
    "up": ecodes.KEY_UP, "down": ecodes.KEY_DOWN,
    "left": ecodes.KEY_LEFT, "right": ecodes.KEY_RIGHT,
    "pageup": ecodes.KEY_PAGEUP, "pagedown": ecodes.KEY_PAGEDOWN,
    "home": ecodes.KEY_HOME, "end": ecodes.KEY_END,
    "tab": ecodes.KEY_TAB, "enter": ecodes.KEY_ENTER,
    "backspace": ecodes.KEY_BACKSPACE, "delete": ecodes.KEY_DELETE,
    "escape": ecodes.KEY_ESC, "shift": ecodes.KEY_LEFTSHIFT,
    "ctrl": ecodes.KEY_LEFTCTRL, "alt": ecodes.KEY_LEFTALT,
    "super": ecodes.KEY_LEFTMETA,
}

ALL_KEY_CODES = list(set(_KEY_MAP.values()))


def _create_device():
    global _device
    cap = {
        ecodes.EV_ABS: [
            (ecodes.ABS_X, AbsInfo(value=0, min=0, max=TOTAL_W - 1, fuzz=0, flat=0, resolution=0)),
            (ecodes.ABS_Y, AbsInfo(value=0, min=0, max=TOTAL_H - 1, fuzz=0, flat=0, resolution=0)),
        ],
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
        ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE] + ALL_KEY_CODES,
    }
    _device = UInput(cap, name="activity-bot-virtual-input", vendor=0xABCD, product=0x1234)
    time.sleep(0.3)  # compositor needs a moment to register the new device


def _close_device():
    global _device
    if _device:
        _device.close()
        _device = None


def _move_abs(x: int, y: int):
    """Move the cursor to absolute (x, y) in the global virtual desktop."""
    x = max(0, min(TOTAL_W - 1, x))
    y = max(0, min(TOTAL_H - 1, y))
    _device.write(ecodes.EV_ABS, ecodes.ABS_X, x)
    _device.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
    _device.syn()


def _move_rel(dx: int, dy: int):
    """Move the cursor by a relative offset."""
    _device.write(ecodes.EV_REL, ecodes.REL_X, dx)
    _device.write(ecodes.EV_REL, ecodes.REL_Y, dy)
    _device.syn()


def _click(button=ecodes.BTN_LEFT):
    _device.write(ecodes.EV_KEY, button, 1)
    _device.syn()
    time.sleep(random.uniform(0.04, 0.12))
    _device.write(ecodes.EV_KEY, button, 0)
    _device.syn()


def _scroll(clicks: int):
    """Scroll wheel: positive = up, negative = down."""
    for _ in range(abs(clicks)):
        _device.write(ecodes.EV_REL, ecodes.REL_WHEEL, 1 if clicks > 0 else -1)
        _device.syn()
        time.sleep(random.uniform(0.03, 0.08))


def _key_tap(code: int):
    _device.write(ecodes.EV_KEY, code, 1)
    _device.syn()
    time.sleep(random.uniform(0.03, 0.09))
    _device.write(ecodes.EV_KEY, code, 0)
    _device.syn()


def _hotkey(*codes: int):
    for c in codes:
        _device.write(ecodes.EV_KEY, c, 1)
        _device.syn()
        time.sleep(random.uniform(0.02, 0.06))
    time.sleep(random.uniform(0.04, 0.10))
    for c in reversed(codes):
        _device.write(ecodes.EV_KEY, c, 0)
        _device.syn()
        time.sleep(random.uniform(0.02, 0.06))


# ---------------------------------------------------------------------------
# Cursor state tracker (we keep our own since Wayland won't tell us)
# ---------------------------------------------------------------------------
_cur_x, _cur_y = 0, 0


def _set_cursor(x, y):
    global _cur_x, _cur_y
    _cur_x, _cur_y = x, y


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SAFE = 60  # stay away from screen edges


def _random_point_on_monitor(mon=None):
    if mon is None:
        mon = random.choice(MONITORS)
    x = random.randint(mon["x"] + SAFE, mon["x"] + mon["w"] - SAFE)
    y = random.randint(mon["y"] + SAFE, mon["y"] + mon["h"] - SAFE)
    return x, y


def _bezier_move(dest_x, dest_y):
    """Smooth Bézier curve mouse movement — looks natural."""
    global _cur_x, _cur_y
    sx, sy = _cur_x, _cur_y
    cx = (sx + dest_x) // 2 + random.randint(-150, 150)
    cy = (sy + dest_y) // 2 + random.randint(-150, 150)
    steps = random.randint(20, 50)
    duration = random.uniform(0.4, 1.8)
    dt = duration / steps

    for i in range(1, steps + 1):
        t = i / steps
        nx = int((1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * dest_x)
        ny = int((1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * dest_y)
        _move_abs(nx, ny)
        _cur_x, _cur_y = nx, ny
        time.sleep(dt + random.uniform(-0.005, 0.005))


def _human_delay():
    base = random.uniform(4, 18)
    if random.random() < 0.12:
        base += random.uniform(10, 35)
    return base


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_mouse_drift():
    """Move cursor smoothly to a random spot (may cross monitors)."""
    x, y = _random_point_on_monitor()
    _bezier_move(x, y)
    return f"drift → ({x},{y})"


def action_small_jiggle():
    """Tiny mouse jitter — hand resting on mouse."""
    dx, dy = random.randint(-20, 20), random.randint(-20, 20)
    steps = random.randint(3, 8)
    for _ in range(steps):
        _move_rel(random.randint(-6, 6), random.randint(-6, 6))
        time.sleep(random.uniform(0.02, 0.08))
    return "jiggle"


def action_mouse_click():
    """Move to random spot, then click."""
    x, y = _random_point_on_monitor()
    _bezier_move(x, y)
    time.sleep(random.uniform(0.08, 0.3))
    _click()
    return f"click @ ({x},{y})"


def action_scroll():
    """Scroll up or down a few notches."""
    n = random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
    _scroll(n)
    return f"scroll {'up' if n > 0 else 'down'} {abs(n)}"


def action_arrow_keys():
    """Press arrow keys like reading code."""
    key = random.choice(["up", "down", "left", "right"])
    n = random.randint(1, 6)
    for _ in range(n):
        _key_tap(_KEY_MAP[key])
        time.sleep(random.uniform(0.08, 0.35))
    return f"arrow {key} ×{n}"


def action_page_scroll():
    """PageUp / PageDown."""
    key = random.choice(["pageup", "pagedown"])
    _key_tap(_KEY_MAP[key])
    return f"{key}"


def action_tab_switch():
    """Switch browser/editor tab."""
    if random.random() < 0.5:
        _hotkey(ecodes.KEY_LEFTCTRL, ecodes.KEY_TAB)
        return "Ctrl+Tab"
    else:
        _hotkey(ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_TAB)
        return "Ctrl+Shift+Tab"


def action_window_switch():
    """Alt+Tab to switch windows."""
    _hotkey(ecodes.KEY_LEFTALT, ecodes.KEY_TAB)
    time.sleep(random.uniform(0.5, 1.5))
    action_small_jiggle()
    return "Alt+Tab"


def action_type_phrase():
    """Type a short phrase then delete it (leaves no trace)."""
    phrases = [
        "checking the logs", "looking into this", "one moment",
        "updating config", "running tests", "reviewing PR",
        "let me check", "on it", "fixing issue", "almost done",
        "syncing changes", "deploying now", "will update shortly",
        "pushed the fix", "restarting service", "merging branch",
    ]
    phrase = random.choice(phrases)
    for ch in phrase:
        code = _KEY_MAP.get(ch)
        if code:
            _key_tap(code)
            time.sleep(random.uniform(0.04, 0.15))
    time.sleep(random.uniform(0.3, 0.8))
    _hotkey(ecodes.KEY_LEFTCTRL, ecodes.KEY_A)
    time.sleep(0.1)
    _key_tap(ecodes.KEY_DELETE)
    return f'typed "{phrase}" + deleted'


def action_keyboard_shortcut():
    """Fire a harmless shortcut."""
    combos = [
        (ecodes.KEY_LEFTCTRL, ecodes.KEY_L),          # focus address bar
        (ecodes.KEY_LEFTCTRL, ecodes.KEY_END),         # scroll to bottom
        (ecodes.KEY_LEFTCTRL, ecodes.KEY_HOME),        # scroll to top
    ]
    combo = random.choice(combos)
    _hotkey(*combo)
    return "shortcut"


def action_monitor_hop():
    """Move cursor to the OTHER monitor — ensures cross-screen activity."""
    if len(MONITORS) < 2:
        return action_mouse_drift()
    current_mon = None
    for m in MONITORS:
        if m["x"] <= _cur_x < m["x"] + m["w"] and m["y"] <= _cur_y < m["y"] + m["h"]:
            current_mon = m
            break
    others = [m for m in MONITORS if m is not current_mon] if current_mon else MONITORS
    target = random.choice(others)
    x, y = _random_point_on_monitor(target)
    _bezier_move(x, y)
    return f"hop → {target['name']} ({x},{y})"


# ---------------------------------------------------------------------------
# Weighted action pool
# ---------------------------------------------------------------------------
ACTIONS = [
    (action_mouse_drift,       20),
    (action_small_jiggle,      18),
    (action_scroll,            14),
    (action_arrow_keys,        10),
    (action_page_scroll,        5),
    (action_tab_switch,         8),
    (action_window_switch,      5),
    (action_mouse_click,        5),
    (action_keyboard_shortcut,  4),
    (action_type_phrase,        3),
    (action_monitor_hop,        8),
]

_actions, _weights = zip(*ACTIONS)


def _pick():
    return random.choices(_actions, weights=_weights, k=1)[0]


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_stop = False


def _on_signal(sig, _frame):
    global _stop
    print("\n[bot] Ctrl+C — shutting down …")
    _stop = True


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run(hours: float):
    global _stop
    _detect_monitors()
    _create_device()

    # Initialise cursor to centre of first monitor
    m0 = MONITORS[0]
    start_x = m0["x"] + m0["w"] // 2
    start_y = m0["y"] + m0["h"] // 2
    _move_abs(start_x, start_y)
    _set_cursor(start_x, start_y)

    end_time = None
    if hours > 0:
        end_time = datetime.now() + timedelta(hours=hours)

    print("Activity bot (Wayland/uinput) — REAL cursor + keyboard")
    print(f"  Monitors: {len(MONITORS)}")
    for i, m in enumerate(MONITORS):
        print(f"    [{i+1}] {m['name']}: {m['w']}×{m['h']} @ ({m['x']},{m['y']})")
    print(f"  Virtual desktop: {TOTAL_W}×{TOTAL_H}")
    if end_time:
        print(f"  Running until {end_time:%H:%M:%S} ({hours}h)")
    else:
        print("  Running forever — Ctrl+C to stop")
    print()

    cycle = 0
    try:
        while not _stop:
            if end_time and datetime.now() >= end_time:
                print("\n[bot] Time limit reached.")
                break

            action = _pick()
            cycle += 1
            now = datetime.now().strftime("%H:%M:%S")
            try:
                detail = action()
            except Exception as exc:
                detail = f"ERROR: {exc}"
            print(f"  [{now}] #{cycle:<5} {action.__name__:<28} {detail}")

            delay = _human_delay()
            time.sleep(delay)

    finally:
        _close_device()
        print(f"\n[bot] Done — {cycle} actions performed.")


def main():
    parser = argparse.ArgumentParser(description="Realistic activity bot (Wayland)")
    parser.add_argument("--hours", type=float, default=8, help="Hours to run (0=forever). Default: 8")
    args = parser.parse_args()
    run(args.hours)


if __name__ == "__main__":
    main()
