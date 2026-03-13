"""BioSync — Lock Screen / Re-auth Challenge"""
import customtkinter as ctk
import threading, datetime
from trust_engine import compute_trust_score, load_baseline
from blockchain_bridge import handle_trust_score

CHALLENGE_PHRASE = "The quick brown fox jumps over the lazy dog"

class LockScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color="#04040a")
        self.app      = app
        self.state    = state
        self.baseline = None
        self.typed_events = []
        self._build()

    def on_show(self):
        import os
        if os.path.exists("models/user_baseline.pkl"):
            self.baseline = load_baseline()
        self.typed_events = []
        self.type_entry.delete(0, "end")
        self.status_lbl.configure(
            text="Type the phrase above to verify your identity",
            text_color="#3a3a55")

    def _build(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Lock icon
        ctk.CTkLabel(center, text="🔒",
            font=("Segoe UI Emoji", 48)).pack(pady=(0,10))
        ctk.CTkLabel(center,
            text="Session Locked",
            font=("Syne", 28, "bold"), text_color="#d4d4f0"
        ).pack()
        ctk.CTkLabel(center,
            text="Anomalous typing pattern detected. Verify to continue.",
            font=("Syne", 13), text_color="#3a3a55"
        ).pack(pady=(6,30))

        # Challenge phrase card
        phrase_card = ctk.CTkFrame(center,
            fg_color="#0d0d14", corner_radius=10,
            border_width=1, border_color="#1e1e2a")
        phrase_card.pack(pady=(0,20), padx=20)
        ctk.CTkLabel(phrase_card,
            text="TYPE THIS PHRASE",
            font=("JetBrains Mono", 9), text_color="#3a3a55"
        ).pack(padx=24, pady=(16,6))
        ctk.CTkLabel(phrase_card,
            text=CHALLENGE_PHRASE,
            font=("JetBrains Mono", 13), text_color="#a78bfa"
        ).pack(padx=24, pady=(0,16))

        # Type entry
        self.type_entry = ctk.CTkEntry(center,
            placeholder_text="start typing here...",
            width=460, height=44,
            fg_color="#0d0d14", border_color="#1e1e2a",
            text_color="#d4d4f0",
            placeholder_text_color="#2e2e40",
            font=("JetBrains Mono", 12), corner_radius=8
        )
        self.type_entry.pack(pady=(0,16))
        self.type_entry.bind("<KeyPress>", self._on_key)
        self.type_entry.bind("<Return>", lambda e: self._verify())

        self.status_lbl = ctk.CTkLabel(center,
            text="Type the phrase above to verify your identity",
            font=("JetBrains Mono", 10), text_color="#3a3a55")
        self.status_lbl.pack(pady=(0,16))

        self.prog_bar = ctk.CTkProgressBar(center,
            width=460, height=3,
            fg_color="#1a1a25", progress_color="#a78bfa")
        self.prog_bar.pack(pady=(0,20))
        self.prog_bar.set(0)

        ctk.CTkButton(center,
            text="Verify Identity  →", height=42, width=220,
            fg_color="#a78bfa", hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 13, "bold"), corner_radius=8,
            command=self._verify
        ).pack()

    def _on_key(self, event):
        import time
        self.typed_events.append({
            'timestamp_ms': int(time.time() * 1000),
            'key': event.char,
            'event_type': 'press'
        })
        typed = self.type_entry.get()
        prog  = min(len(typed) / len(CHALLENGE_PHRASE), 1.0)
        self.prog_bar.set(prog)

    def _verify(self):
        typed = self.type_entry.get().strip()
        if typed != CHALLENGE_PHRASE:
            self.status_lbl.configure(
                text="⚠ Phrase doesn't match. Try again.",
                text_color="#f87171"); return
        if not self.typed_events:
            self.status_lbl.configure(
                text="⚠ No keystrokes captured",
                text_color="#f87171"); return
        self.status_lbl.configure(
            text="⏳ Analysing typing pattern...",
            text_color="#fbbf24")
        threading.Thread(target=self._check_pattern, daemon=True).start()

    def _check_pattern(self):
        result = compute_trust_score(self.typed_events, self.baseline)
        score  = result['score']
        if score >= 60:
            handle_trust_score(self.state['session_id'],
                               score, "RESTORE")
            self.after(0, lambda: (
                self.status_lbl.configure(
                    text=f"✓ Identity confirmed — score {score:.0f}",
                    text_color="#4ade80"),
                self.after(1200, lambda: self.app.show_screen("dashboard"))
            ))
        else:
            self.after(0, lambda: self.status_lbl.configure(
                text=f"✗ Pattern mismatch — score {score:.0f}. Try again.",
                text_color="#f87171"))