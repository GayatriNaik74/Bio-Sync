"""BioSync — Live Dashboard Screen"""
import customtkinter as ctk
import threading, joblib, datetime, os
from trust_engine       import compute_trust_score, load_baseline
from lock_manager       import should_lock, lock_workstation
from blockchain_bridge  import handle_trust_score

# Keystroke buffer — capture.py fills this in real-time
_event_buffer = []

def push_event(evt): _event_buffer.append(evt)

class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color="#07070b")
        self.app        = app
        self.state      = state
        self.baseline   = None
        self.monitoring = False
        self.events_log = []
        self._build()

    def on_show(self):
        # Load baseline when screen appears
        if os.path.exists("models/user_baseline.pkl"):
            self.baseline = load_baseline()
            self.monitoring = True
            self._update_loop()
        self.user_lbl.configure(
            text=f"● {self.state.get('username','user')}")

    def _build(self):
        # ── Sidebar ─────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self,
            width=200, fg_color="#0a0a10", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="⬡  BIOSYNC",
            font=("JetBrains Mono", 13, "bold"),
            text_color="#a78bfa").pack(pady=(24,4), padx=20, anchor="w")
        self.user_lbl = ctk.CTkLabel(self.sidebar,
            text="● user",
            font=("JetBrains Mono", 10), text_color="#3a3a55")
        self.user_lbl.pack(padx=20, anchor="w", pady=(0,24))

        for (label, icon, cmd) in [
            ("Dashboard", "▣", lambda: None),
            ("Profile",   "◎", lambda: self.app.show_screen("profile")),
            ("Enroll",    "◈", lambda: self.app.show_screen("enrollment")),
            ("Lock",      "⊠", lambda: self.app.show_screen("lock")),
        ]:
            ctk.CTkButton(self.sidebar,
                text=f"  {icon}  {label}",
                height=38, anchor="w",
                fg_color="transparent", hover_color="#141420",
                text_color="#3a3a55",
                font=("Syne", 12), corner_radius=6,
                command=cmd
            ).pack(fill="x", padx=12, pady=2)

        # ── Main area ────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", expand=True, fill="both", padx=30, pady=30)

        # ── Top row: score + status ──────────────────────
        top = ctk.CTkFrame(main, fg_color="transparent")
        top.pack(fill="x", pady=(0,20))

        # Trust score card
        from ui.gauge import TrustGauge

        score_card = ctk.CTkFrame(top,
            fg_color="#0d0d14", corner_radius=12,
            border_width=1, border_color="#1e1e2a")
        score_card.pack(side="left", padx=(0, 16))

        self.gauge = TrustGauge(score_card, size=240, bg="#0d0d14")
        self.gauge.pack(padx=10, pady=(10, 4))

        self.score_lbl = ctk.CTkLabel(score_card,
            text="—",
            font=("Syne", 13, "bold"),
            text_color="#3a3a55")
        self.score_lbl.pack(pady=(0, 14))

        # Stats panel
        stats = ctk.CTkFrame(top,
            fg_color="#0d0d14", corner_radius=12,
            border_width=1, border_color="#1e1e2a")
        stats.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(stats, text="SESSION STATS",
            font=("JetBrains Mono", 9), text_color="#3a3a55"
        ).pack(padx=20, pady=(18,10), anchor="w")

        self.stats_labels = {}
        for key, val in [("Keypresses","0"),("Anomalies","0"),
                          ("Locked","0"),("Uptime","0s")]:
            row = ctk.CTkFrame(stats, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=key,
                font=("JetBrains Mono", 10),
                text_color="#2e2e40", anchor="w"
            ).pack(side="left")
            lbl = ctk.CTkLabel(row, text=val,
                font=("JetBrains Mono", 10),
                text_color="#d4d4f0", anchor="e")
            lbl.pack(side="right")
            self.stats_labels[key] = lbl

        # ── Event log ────────────────────────────────────
        ctk.CTkLabel(main, text="LIVE EVENTS",
            font=("JetBrains Mono", 9), text_color="#3a3a55", anchor="w"
        ).pack(anchor="w", pady=(0,6))
        self.log_box = ctk.CTkTextbox(main,
            height=180, fg_color="#0a0a10",
            text_color="#4a4a6a",
            font=("JetBrains Mono", 11),
            corner_radius=8, border_width=1,
            border_color="#1e1e2a", state="disabled"
        )
        self.log_box.pack(fill="x")

        # ── Score history bar ────────────────────────────
        self.bar_canvas = ctk.CTkCanvas(main,
            height=40, bg="#0a0a10",
            highlightthickness=0)
        self.bar_canvas.pack(fill="x", pady=(12,0))
        self.score_history = []
        self.start_time    = datetime.datetime.now()
        self.anomaly_count = 0
        self.lock_count    = 0
        self.keypress_count= 0

    def _update_loop(self):
        if not self.monitoring: return
        threading.Thread(target=self._score_tick, daemon=True).start()
        self.after(15000, self._update_loop)

    def _score_tick(self):
        global _event_buffer
        events = _event_buffer.copy()
        _event_buffer.clear()
        if not self.baseline: return
        result = compute_trust_score(events, self.baseline)
        self.state['trust_score'] = result['score']
        self.state['risk_level']  = result['risk']
        self.keypress_count += result['keystrokes']
        self.after(0, lambda: self._refresh_ui(result))
        # Blockchain log + lock
        handle_trust_score(
            self.state['session_id'],
            result['score'], result['risk'])
        if should_lock(result['score']):
            self.lock_count += 1
            self.after(0, lambda: self.app.show_screen("lock"))

    def _refresh_ui(self, result):
        score = result['score']
        risk  = result['risk']
        color = {'LOW':"#4ade80", 'MEDIUM':"#fbbf24", 'HIGH':"#f87171"}[risk]
        self.gauge.set_score(score) 
        self.score_lbl.configure(text=f"{score:.0f}", text_color=color)
        self.risk_lbl.configure(text=risk, text_color=color)
        uptime = (int((datetime.datetime.now()-self.start_time).total_seconds()))
        self.stats_labels["Keypresses"].configure(text=str(self.keypress_count))
        self.stats_labels["Anomalies"].configure(text=str(self.anomaly_count))
        self.stats_labels["Locked"].configure(text=str(self.lock_count))
        self.stats_labels["Uptime"].configure(text=f"{uptime}s")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log(f"[{ts}] score={score:.1f}  risk={risk}  keys={result['keystrokes']}")
        self.score_history.append(score)
        if len(self.score_history) > 60: self.score_history.pop(0)
        self._draw_history()

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("0.0", msg + "\n")
        self.log_box.configure(state="disabled")

    def _draw_history(self):
        c = self.bar_canvas; c.delete("all")
        w = c.winfo_width(); h = 40
        n = len(self.score_history)
        if n < 2: return
        bw = w / n
        for i, s in enumerate(self.score_history):
            col = "#4ade80" if s>=80 else ("#fbbf24" if s>=60 else "#f87171")
            bh = int(s / 100 * (h-6)) + 3
            c.create_rectangle(i*bw+1, h-bh, (i+1)*bw-1, h,
                                fill=col, outline="")