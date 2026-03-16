"""
BioSync — Lock Screen
Appears automatically when trust score drops.
Verifies identity by analysing TYPING PATTERN of challenge phrase
not just checking if the phrase text matches.
"""

import sys, os
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', 'src'))

import customtkinter as ctk
import threading, time
from trust_engine  import compute_trust_score, load_baseline
from lock_manager  import reset_lock_counter

try:
    from blockchain_bridge import handle_trust_score
    _HAS_BLOCKCHAIN = True
except Exception:
    _HAS_BLOCKCHAIN = False

CHALLENGE = "The quick brown fox jumps over the lazy dog"

C_BG     = "#04040a"
C_CARD   = "#0d0d16"
C_BORDER = "#1c1c28"
C_DIM    = "#2e2e44"
C_BRIGHT = "#d4d4f0"
C_PURPLE = "#a78bfa"
C_GREEN  = "#4ade80"
C_AMBER  = "#fbbf24"
C_RED    = "#f87171"


class LockScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color=C_BG)
        self.app          = app
        self.state        = state
        self.baseline     = None
        self.typed_events = []
        self._press_times = {}
        self._last_press  = None
        self._build()

    def on_show(self):
        if os.path.exists("models/user_baseline.pkl"):
            self.baseline = load_baseline()
        self.typed_events = []
        self._press_times = {}
        self._last_press  = None
        self.type_entry.delete(0, "end")
        self.prog_bar.set(0)
        self.status_lbl.configure(
            text="Type the phrase above to verify "
                 "your identity",
            text_color=C_DIM)
        self.type_entry.focus()

    def _build(self):
        center = ctk.CTkFrame(self,
                              fg_color="transparent")
        center.place(relx=0.5, rely=0.5,
                     anchor="center")

        ctk.CTkLabel(center, text="🔒",
            font=("Segoe UI Emoji", 52)
        ).pack(pady=(0, 10))

        ctk.CTkLabel(center,
            text="Session Locked",
            font=("Syne", 28, "bold"),
            text_color=C_BRIGHT
        ).pack()

        ctk.CTkLabel(center,
            text="Anomalous typing pattern detected."
                 "  Verify your identity to continue.",
            font=("Syne", 13),
            text_color=C_DIM
        ).pack(pady=(6, 30))

        # Challenge phrase card
        pc = ctk.CTkFrame(center,
            fg_color=C_CARD, corner_radius=10,
            border_width=1, border_color=C_BORDER)
        pc.pack(pady=(0, 20), padx=20)

        ctk.CTkLabel(pc,
            text="TYPE THIS PHRASE NATURALLY",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(padx=24, pady=(16, 6))

        ctk.CTkLabel(pc,
            text=CHALLENGE,
            font=("JetBrains Mono", 13),
            text_color=C_PURPLE
        ).pack(padx=24, pady=(0, 16))

        # Input field
        self.type_entry = ctk.CTkEntry(center,
            placeholder_text="type here...",
            width=480, height=44,
            fg_color=C_CARD,
            border_color=C_BORDER,
            text_color=C_BRIGHT,
            placeholder_text_color=C_DIM,
            font=("JetBrains Mono", 12),
            corner_radius=8)
        self.type_entry.pack(pady=(0, 16))
        self.type_entry.bind("<KeyPress>",
                             self._on_keypress)
        self.type_entry.bind("<KeyRelease>",
                             self._on_keyrelease)
        self.type_entry.bind("<Return>",
            lambda e: self._verify())

        self.status_lbl = ctk.CTkLabel(center,
            text="Type the phrase above naturally"
                 " — your rhythm will be analysed",
            font=("JetBrains Mono", 10),
            text_color=C_DIM)
        self.status_lbl.pack(pady=(0, 16))

        self.prog_bar = ctk.CTkProgressBar(center,
            width=480, height=3,
            fg_color="#1a1a25",
            progress_color=C_PURPLE)
        self.prog_bar.pack(pady=(0, 20))
        self.prog_bar.set(0)

        ctk.CTkButton(center,
            text="Verify Identity  →",
            height=42, width=220,
            fg_color=C_PURPLE,
            hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 13, "bold"),
            corner_radius=8,
            command=self._verify
        ).pack()

    def _on_keypress(self, event):
        now_ms = int(time.time() * 1000)

        if event.keysym in (
            "Shift_L","Shift_R","Control_L",
            "Control_R","Alt_L","Alt_R",
            "BackSpace","Return","Tab","Escape",
            "Delete","Left","Right","Up","Down"):
            return

        key = event.char
        if not key or not key.isprintable():
            return

        flight = (now_ms - self._last_press
                  ) if self._last_press else 0
        self._last_press     = now_ms
        self._press_times[key] = now_ms

        self.typed_events.append({
            'timestamp_ms': now_ms,
            'key'         : key,
            'event_type'  : 'press',
            'flight_ms'   : flight,
        })

        typed = self.type_entry.get()
        prog  = min(len(typed) / len(CHALLENGE), 1.0)
        self.prog_bar.set(prog)

    def _on_keyrelease(self, event):
        now_ms = int(time.time() * 1000)
        key    = event.char
        if not key or not key.isprintable():
            return
        press_t = self._press_times.pop(
            key, now_ms - 80)
        dwell   = now_ms - press_t
        for evt in reversed(self.typed_events):
            if (evt['key'] == key and
                    'dwell_ms' not in evt):
                evt['dwell_ms'] = dwell
                break

    def _verify(self):
        typed = self.type_entry.get().strip()

        if len(typed) < 10:
            self.status_lbl.configure(
                text="⚠ Please type more of the phrase",
                text_color=C_AMBER)
            return

        if len(self.typed_events) < 5:
            self.status_lbl.configure(
                text="⚠ Not enough keystrokes captured."
                     " Type more.",
                text_color=C_RED)
            return

        self.status_lbl.configure(
            text="⏳ Analysing your typing pattern...",
            text_color=C_AMBER)
        threading.Thread(
            target=self._check,
            daemon=True).start()

    def _check(self):
        if not self.baseline:
            self.after(0, lambda: self.status_lbl.configure(
                text="⚠ No baseline model found.",
                text_color=C_RED))
            return

        result = compute_trust_score(
            self.typed_events, self.baseline)
        score  = result['score']
        risk   = result['risk']

        print(f"  Lock screen verify: score={score}, "
              f"risk={risk}, "
              f"keys={result['keystrokes']}")

        # Identity confirmed if score >= 60
        if score >= 60:
            reset_lock_counter()

            if _HAS_BLOCKCHAIN:
                try:
                    handle_trust_score(
                        self.state.get(
                            'session_id', 'sess'),
                        score, "RESTORE")
                except Exception:
                    pass

            self.after(0, lambda: (
                self.status_lbl.configure(
                    text=f"✓ Identity confirmed  "
                         f"— score {score:.0f}",
                    text_color=C_GREEN),
                self.after(1200, lambda:
                    self.app.show_screen("dashboard"))
            ))
        else:
            self.after(0, lambda:
                self.status_lbl.configure(
                    text=f"✗ Pattern mismatch "
                         f"— score {score:.0f}. "
                         f"Try again naturally.",
                    text_color=C_RED))
            # Clear and let user retry
            self.after(0, lambda: (
                self.typed_events.clear(),
                self.type_entry.delete(0, "end"),
                self.prog_bar.set(0)
            ))