"""
BioSync — Dashboard Screen (Final)
Layout inspired by reference design:
  - Sidebar navigation
  - Integrity gauge (arc style)
  - 6 parameter cards (dwell, flight, accuracy, etc.)
  - Threat level timeline
  - Intrusion / anomaly log
  - Recent activity feed
  - Score history bar
"""

import customtkinter as ctk
import tkinter as tk
import threading, datetime, os, math

from trust_engine      import compute_trust_score, load_baseline
from lock_manager      import should_lock
from blockchain_bridge import handle_trust_score

# ── Keystroke buffer ─────────────────────────────────
_event_buffer = []
def push_event(evt): _event_buffer.append(evt)

# ── Colours ───────────────────────────────────────────
C_BG     = "#07070b"
C_CARD   = "#0d0d14"
C_SIDE   = "#0a0a10"
C_BORDER = "#1e1e2a"
C_DIM    = "#3a3a55"
C_BRIGHT = "#d4d4f0"
C_PURPLE = "#a78bfa"
C_GREEN  = "#4ade80"
C_AMBER  = "#fbbf24"
C_RED    = "#f87171"
C_BLUE   = "#60a5fa"


# ═══════════════════════════════════════════════════════
# ARC GAUGE  (matches reference style)
# ═══════════════════════════════════════════════════════
class IntegrityGauge(tk.Canvas):
    def __init__(self, parent, size=220,
                 bg=C_CARD, **kw):
        self.SIZE = size
        super().__init__(parent,
            width=size,
            height=size // 2 + 44,
            bg=bg,
            highlightthickness=0, **kw)
        self._score   = 100.0
        self._cur     = 100.0
        self._anim_id = None
        self.after(60, lambda: self._draw(self._cur))

    # colour helpers
    def _score_color(self, s):
        return (C_GREEN  if s >= 68
                else C_AMBER if s >= 52
                else C_RED)

    def _risk_label(self, s):
        return ("LOW RISK"    if s >= 68
                else "MEDIUM RISK" if s >= 52
                else "HIGH RISK")

    def _draw(self, score):
        self.delete("all")
        sz = self.SIZE
        cx = sz // 2
        cy = sz // 2 + 10
        r  = sz // 2 - 18
        col = self._score_color(score)

        # ── Background arc ────────────────────────
        self.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=0, extent=180,
            style="arc",
            outline="#1e1e2a", width=14)

        # ── Coloured score arc ────────────────────
        extent = (score / 100) * 180
        # gradient segments red→amber→green
        STEPS = 60
        for i in range(STEPS):
            t0 = i / STEPS
            t1 = (i + 1) / STEPS
            if t0 * 100 > score:
                break
            seg_col = self._arc_color(t0)
            a0 = 180 - t0 * 180
            a1 = 180 - t1 * 180
            self.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=a0,
                extent=-(a0 - a1),
                style="arc",
                outline=seg_col,
                width=14)

        # ── Score text ────────────────────────────
        self.create_text(cx, cy - 18,
            text=f"{int(round(score))}",
            fill=col,
            font=("JetBrains Mono", 28, "bold"),
            anchor="center")
        self.create_text(cx, cy + 8,
            text="/ 100",
            fill="#2e2e44",
            font=("JetBrains Mono", 9),
            anchor="center")
        self.create_text(cx, cy + 30,
            text=self._risk_label(score),
            fill=col,
            font=("JetBrains Mono", 9, "bold"),
            anchor="center")

    def _arc_color(self, t):
        stops = [
            (0.00, (220, 50,  50)),
            (0.30, (230, 140, 20)),
            (0.55, (220, 200, 20)),
            (0.78, (130, 200, 30)),
            (1.00, (40,  200, 70)),
        ]
        lo, hi = stops[0], stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i+1][0]:
                lo, hi = stops[i], stops[i+1]
                break
        span = hi[0] - lo[0]
        f    = 0.0 if span == 0 else (t - lo[0]) / span
        r = int(lo[1][0] + (hi[1][0]-lo[1][0])*f)
        g = int(lo[1][1] + (hi[1][1]-lo[1][1])*f)
        b = int(lo[1][2] + (hi[1][2]-lo[1][2])*f)
        return f"#{r:02x}{g:02x}{b:02x}"

    def set_score(self, score: float):
        self._score = max(0.0, min(100.0, float(score)))
        if self._anim_id:
            self.after_cancel(self._anim_id)
        self._animate()

    def _animate(self):
        diff = self._score - self._cur
        if abs(diff) < 0.4:
            self._cur = self._score
            self._draw(self._cur)
            return
        self._cur += diff * 0.14
        self._draw(self._cur)
        self._anim_id = self.after(16, self._animate)


# ═══════════════════════════════════════════════════════
# THREAT TIMELINE
# ═══════════════════════════════════════════════════════
class ThreatTimeline(tk.Canvas):
    def __init__(self, parent, bg=C_CARD, **kw):
        super().__init__(parent, bg=bg,
                         highlightthickness=0, **kw)
        self.points = []
        self.bind("<Configure>", lambda e: self.redraw())

    def add_point(self, score: float, label: str = ""):
        self.points.append((score, label))
        if len(self.points) > 80:
            self.points.pop(0)
        self.redraw()

    def redraw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 20 or H < 20 or len(self.points) < 2:
            return

        PL, PR = 36, 12
        PT, PB = 10, 22
        gw = W - PL - PR
        gh = H - PT - PB

        def sy(s):
            return PT + gh * (1 - s / 100)

        # Zone bands
        self.create_rectangle(PL, sy(52),
            PL+gw, PT+gh, fill="#1a0808", outline="")
        self.create_rectangle(PL, sy(68),
            PL+gw, sy(52), fill="#1a1200", outline="")
        self.create_rectangle(PL, PT,
            PL+gw, sy(68), fill="#081a08", outline="")

        # Threshold lines
        for thr, col in [(68, "#4ade8040"),
                         (52, "#f8717140")]:
            y = sy(thr)
            self.create_line(PL, y, PL+gw, y,
                fill=col, width=1, dash=(4, 4))

        # Y labels
        for val, lbl in [(100,"100"),(68,"68"),
                         (52,"52"),(0,"0")]:
            self.create_text(PL-4, sy(val),
                text=lbl, fill="#2e2e44",
                font=("JetBrains Mono", 7),
                anchor="e")

        # Grid
        for val in [25, 50, 75, 100]:
            self.create_line(PL, sy(val),
                PL+gw, sy(val),
                fill="#111118", width=1)

        n   = len(self.points)
        pts = []
        for i, (score, _) in enumerate(self.points):
            x = PL + (i / (n-1)) * gw
            pts.append((x, sy(score)))

        # Coloured line segments
        for i in range(len(pts)-1):
            avg = (self.points[i][0] +
                   self.points[i+1][0]) / 2
            col = (C_GREEN  if avg >= 68
                   else C_AMBER if avg >= 52
                   else C_RED)
            self.create_line(
                pts[i][0], pts[i][1],
                pts[i+1][0], pts[i+1][1],
                fill=col, width=2,
                capstyle="round")

        # Dots
        for i, (x, y) in enumerate(pts):
            s   = self.points[i][0]
            col = (C_GREEN  if s >= 68
                   else C_AMBER if s >= 52
                   else C_RED)
            self.create_oval(x-3, y-3,
                x+3, y+3, fill=col, outline="")

        # Current dot (larger)
        if pts:
            lx, ly = pts[-1]
            ls  = self.points[-1][0]
            col = (C_GREEN  if ls >= 68
                   else C_AMBER if ls >= 52
                   else C_RED)
            self.create_oval(lx-5, ly-5,
                lx+5, ly+5,
                fill=col, outline=C_BG, width=2)

        # X labels
        for idx, anch in [(0,"w"),
                          (n//2,"center"),
                          (n-1,"e")]:
            if idx < n:
                x = PL + (idx / max(n-1,1)) * gw
                self.create_text(
                    x, H-PB+8,
                    text=self.points[idx][1],
                    fill="#2e2e44",
                    font=("JetBrains Mono", 7),
                    anchor=anch)

        # Border
        self.create_rectangle(PL, PT,
            PL+gw, PT+gh,
            outline="#1e1e2a", width=1)


# ═══════════════════════════════════════════════════════
# DASHBOARD SCREEN
# ═══════════════════════════════════════════════════════
class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color=C_BG)
        self.app            = app
        self.state          = state
        self.baseline       = None
        self.monitoring     = False
        self.start_time     = datetime.datetime.now()
        self.anomaly_count  = 0
        self.lock_count     = 0
        self.keypress_count = 0
        self.score_history  = []
        self.intrusion_log  = []
        self.activity_log   = []
        self.last_dwell     = 0.0
        self.last_flight    = 0.0
        self.last_accuracy  = 0.0
        self.wpm            = 0.0
        self._build()

    # ─────────────────────────────────────────────────
    def on_show(self):
        if os.path.exists("models/user_baseline.pkl"):
            self.baseline   = load_baseline()
            self.monitoring = True
            self._update_loop()
        uname = self.state.get('username', 'user')
        self.user_lbl.configure(text=uname)
        self.start_time = datetime.datetime.now()
        sid = self.state.get('session_id', '—')
        self._add_activity("User authenticated", C_BLUE)
        self._add_activity("Biometric model loaded", C_GREEN)

    # ─────────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────────
    def _build(self):

        # ════════════════════════
        # SIDEBAR
        # ════════════════════════
        sb = ctk.CTkFrame(self, width=200,
            fg_color=C_SIDE, corner_radius=0)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Logo
        ctk.CTkLabel(sb,
            text="🛡  BioSync",
            font=("Syne", 16, "bold"),
            text_color=C_BLUE
        ).pack(pady=(22, 28), padx=18, anchor="w")

        # Nav
        nav = [
            ("📊  Dashboard",   None),
            ("👤  Profile",     lambda: self.app.show_screen("profile")),
            ("📄  Security Log",lambda: self._focus_log()),
            ("◈   Re-enroll",   lambda: self.app.show_screen("enrollment")),
            ("⊠   Lock",        lambda: self.app.show_screen("lock")),
        ]
        for label, cmd in nav:
            active = cmd is None
            ctk.CTkButton(sb,
                text=label, height=38, anchor="w",
                fg_color=("#1e3a5f" if active
                          else "transparent"),
                hover_color="#1e3a5f",
                text_color=("white" if active
                            else C_DIM),
                font=("Syne", 12),
                corner_radius=8,
                command=cmd if cmd else lambda: None
            ).pack(fill="x", padx=10, pady=2)

        # User info bottom
        ctk.CTkLabel(sb,
            text="BioSync  v1.0",
            font=("JetBrains Mono", 8),
            text_color="#1e1e2a"
        ).pack(side="bottom", pady=(0, 8))

        ctk.CTkButton(sb,
            text="⏻  Logout",
            height=34, anchor="w",
            fg_color="transparent",
            hover_color="#1a0a0a",
            text_color=C_RED,
            font=("Syne", 11),
            corner_radius=6,
            command=lambda: self.app.show_screen("login")
        ).pack(side="bottom", fill="x",
               padx=10, pady=2)

        ctk.CTkFrame(sb, height=1,
            fg_color=C_BORDER
        ).pack(side="bottom", fill="x",
               padx=14, pady=4)

        ub = ctk.CTkFrame(sb, fg_color="transparent")
        ub.pack(side="bottom", fill="x",
                padx=14, pady=6)
        ctk.CTkLabel(ub,
            text="👤",
            font=("Segoe UI Emoji", 14)
        ).pack(side="left", padx=(0, 8))
        col2 = ctk.CTkFrame(ub,
                            fg_color="transparent")
        col2.pack(side="left")
        self.user_lbl = ctk.CTkLabel(col2,
            text="—",
            font=("Syne", 12),
            text_color=C_BRIGHT)
        self.user_lbl.pack(anchor="w")
        ctk.CTkLabel(col2,
            text="Enrolled",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(anchor="w")

        # ════════════════════════
        # SCROLLABLE MAIN
        # ════════════════════════
        scroll = ctk.CTkScrollableFrame(self,
            fg_color=C_BG,
            scrollbar_button_color="#1e1e2a",
            scrollbar_button_hover_color="#2e2e44")
        scroll.pack(side="left", expand=True,
                    fill="both")

        main = ctk.CTkFrame(scroll,
                            fg_color="transparent")
        main.pack(fill="both", expand=True,
                  padx=24, pady=16)

        # Header
        ctk.CTkLabel(main,
            text="Security Dashboard",
            font=("Syne", 22, "bold"),
            text_color="white"
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(main,
            text="Biometric profile active  ·  "
                 "Continuous monitoring enabled",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(anchor="w", pady=(0, 16))

        # ── Gauge + status ────────────────────────
        gauge_card = ctk.CTkFrame(main,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        gauge_card.pack(fill="x", pady=(0, 12))

        self.gauge = IntegrityGauge(
            gauge_card, size=240, bg=C_CARD)
        self.gauge.pack(pady=(20, 6))

        self.status_lbl = ctk.CTkLabel(gauge_card,
            text="● No intrusion detected",
            font=("Syne", 12, "bold"),
            text_color=C_GREEN)
        self.status_lbl.pack(pady=(0, 16))

        # ── 6 Parameter cards ─────────────────────
        cards_frame = ctk.CTkFrame(main,
                                   fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 12))

        self.param_labels = {}
        params = [
            ("⚡  Avg Speed",   "wpm",      "0 WPM",  C_BLUE),
            ("✓   Accuracy",    "accuracy", "—",      C_GREEN),
            ("📊  Rhythm",      "rhythm",   "—",      C_BLUE),
            ("⏱   Key Hold",    "dwell",    "— ms",   C_DIM),
            ("✈   Flight",      "flight",   "— ms",   C_DIM),
            ("⚠   Risk Level",  "risk",     "LOW",    C_GREEN),
        ]
        for i, (label, key, default, color) in \
                enumerate(params):
            row = i // 3
            col = i % 3
            card = ctk.CTkFrame(cards_frame,
                fg_color=C_CARD,
                corner_radius=10,
                border_width=1,
                border_color=C_BORDER)
            card.grid(row=row, column=col,
                      padx=5, pady=5, sticky="nsew")
            cards_frame.columnconfigure(col, weight=1)
            ctk.CTkLabel(card, text=label,
                font=("Syne", 11),
                text_color=color
            ).pack(anchor="w", padx=14, pady=(12, 2))
            lbl = ctk.CTkLabel(card, text=default,
                font=("Syne", 20, "bold"),
                text_color="white")
            lbl.pack(anchor="w", padx=14,
                     pady=(0, 12))
            self.param_labels[key] = lbl

        # ── Threat timeline ───────────────────────
        tl_card = ctk.CTkFrame(main,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        tl_card.pack(fill="x", pady=(0, 12))

        tl_top = ctk.CTkFrame(tl_card,
                              fg_color="transparent")
        tl_top.pack(fill="x", padx=16,
                    pady=(12, 4))
        ctk.CTkLabel(tl_top,
            text="Threat Level Timeline",
            font=("Syne", 13, "bold"),
            text_color="white"
        ).pack(side="left")
        leg = ctk.CTkFrame(tl_top,
                           fg_color="transparent")
        leg.pack(side="right")
        for col, lbl in [(C_GREEN,"LOW"),
                         (C_AMBER,"MED"),
                         (C_RED,"HIGH")]:
            ctk.CTkLabel(leg, text="●  ",
                font=("JetBrains Mono", 9),
                text_color=col
            ).pack(side="left")
            ctk.CTkLabel(leg, text=lbl+"   ",
                font=("JetBrains Mono", 8),
                text_color=C_DIM
            ).pack(side="left")

        self.timeline = ThreatTimeline(
            tl_card, bg=C_CARD, height=120)
        self.timeline.pack(
            fill="x", padx=12, pady=(0, 12))

        # ── Score history bar ─────────────────────
        hist_card = ctk.CTkFrame(main,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        hist_card.pack(fill="x", pady=(0, 12))

        ht = ctk.CTkFrame(hist_card,
                          fg_color="transparent")
        ht.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(ht,
            text="Score History",
            font=("Syne", 13, "bold"),
            text_color="white"
        ).pack(side="left")
        ctk.CTkLabel(ht,
            text="last 60 readings",
            font=("JetBrains Mono", 8),
            text_color="#1e1e2a"
        ).pack(side="right")

        self.bar_canvas = tk.Canvas(hist_card,
            height=40, bg=C_CARD,
            highlightthickness=0)
        self.bar_canvas.pack(
            fill="x", padx=12, pady=(0, 12))

        # ── Intrusion log ─────────────────────────
        log_card = ctk.CTkFrame(main,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        log_card.pack(fill="x", pady=(0, 12))

        lt = ctk.CTkFrame(log_card,
                          fg_color="transparent")
        lt.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(lt,
            text="Security Logs",
            font=("Syne", 13, "bold"),
            text_color="white"
        ).pack(side="left")
        ctk.CTkButton(lt,
            text="Clear", width=52, height=22,
            fg_color="transparent",
            border_width=1,
            border_color=C_BORDER,
            text_color=C_DIM,
            font=("JetBrains Mono", 8),
            hover_color="#1a1a28",
            command=self._clear_log
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(log_card,
            height=130,
            fg_color="#0a0a10",
            text_color="#4a4a6a",
            font=("JetBrains Mono", 10),
            corner_radius=8,
            border_width=1,
            border_color=C_BORDER,
            state="disabled")
        self.log_box.pack(
            fill="x", padx=12, pady=(0, 12))
        self.log_box.tag_config(
            "HIGH",   foreground=C_RED)
        self.log_box.tag_config(
            "MEDIUM", foreground=C_AMBER)
        self.log_box.tag_config(
            "LOW",    foreground=C_GREEN)

        # ── Recent activity ───────────────────────
        act_card = ctk.CTkFrame(main,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        act_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(act_card,
            text="Recent Activity",
            font=("Syne", 13, "bold"),
            text_color="white"
        ).pack(anchor="w", padx=16, pady=(14, 6))

        self.activity_frame = ctk.CTkFrame(act_card,
            fg_color="transparent")
        self.activity_frame.pack(
            fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(act_card, text="",
                     height=4).pack()

    # ─────────────────────────────────────────────────
    # UPDATE LOOP
    # ─────────────────────────────────────────────────
    def _update_loop(self):
        if not self.monitoring:
            return
        threading.Thread(
            target=self._score_tick,
            daemon=True
        ).start()
        self.after(15000, self._update_loop)

    def _score_tick(self):
        global _event_buffer
        events = _event_buffer.copy()
        _event_buffer.clear()
        if not self.baseline:
            return

        result = compute_trust_score(
            events, self.baseline)
        self.state['trust_score'] = result['score']
        self.state['risk_level']  = result['risk']
        self.keypress_count += result.get(
            'keystrokes', 0)

        dwells  = [e.get('dwell_ms',  0)
                   for e in events
                   if e.get('dwell_ms',  0) > 0]
        flights = [e.get('flight_ms', 0)
                   for e in events
                   if e.get('flight_ms', 0) > 0]
        if dwells:
            self.last_dwell = sum(dwells)/len(dwells)
        if flights:
            self.last_flight = sum(flights)/len(flights)

        # WPM estimate
        up = max(1, (datetime.datetime.now() -
                     self.start_time).total_seconds())
        self.wpm = round((self.keypress_count / 5)
                         / (up / 60), 1)

        risk = result['risk']
        if risk in ('MEDIUM', 'HIGH'):
            self.anomaly_count += 1
            ts = datetime.datetime.now()
            entry = {
                'time'  : ts.strftime("%H:%M:%S"),
                'score' : result['score'],
                'risk'  : risk,
                'dwell' : self.last_dwell,
                'flight': self.last_flight,
            }
            self.intrusion_log.append(entry)
            self.after(0,
                lambda e=entry: self._add_intrusion(e))
            self.after(0, lambda r=risk:
                self._add_activity(
                    f"Anomaly detected — risk={r}",
                    C_RED if r=='HIGH' else C_AMBER))

        try:
            handle_trust_score(
                self.state.get('session_id', 'sess'),
                result['score'], risk)
        except Exception:
            pass

        if should_lock(result['score']):
            self.lock_count += 1
            self.after(0,
                lambda: self._add_activity(
                    "Session locked", C_RED))
            self.after(0,
                lambda: self.app.show_screen("lock"))

        self.after(0,
            lambda: self._refresh_ui(result))

    # ─────────────────────────────────────────────────
    # REFRESH UI
    # ─────────────────────────────────────────────────
    def _refresh_ui(self, result):
        score = result['score']
        risk  = result['risk']
        color = {
            'LOW'   : C_GREEN,
            'MEDIUM': C_AMBER,
            'HIGH'  : C_RED,
        }.get(risk, C_PURPLE)

        # Gauge
        self.gauge.set_score(score)

        # Status banner
        if risk == 'HIGH':
            self.status_lbl.configure(
                text="⚠  Intrusion detected!",
                text_color=C_RED)
        elif risk == 'MEDIUM':
            self.status_lbl.configure(
                text="⚠  Anomalous activity",
                text_color=C_AMBER)
        else:
            self.status_lbl.configure(
                text="●  No intrusion detected",
                text_color=C_GREEN)

        # Uptime
        up  = int((datetime.datetime.now() -
                   self.start_time).total_seconds())
        h, rem = divmod(up, 3600)
        m, s   = divmod(rem, 60)
        uptime = (f"{h}h {m}m" if h
                  else f"{m}m {s}s" if m
                  else f"{s}s")

        # Parameter cards
        rhythm = max(0, 100 - int(
            self.last_dwell / 5)) if self.last_dwell > 0 else 0

        self.param_labels['wpm'].configure(
            text=f"{self.wpm:.0f} WPM")
        self.param_labels['accuracy'].configure(
            text=f"{int(score)}%")
        self.param_labels['rhythm'].configure(
            text=f"{rhythm}%")
        self.param_labels['dwell'].configure(
            text=f"{self.last_dwell:.0f} ms")
        self.param_labels['flight'].configure(
            text=f"{self.last_flight:.0f} ms")
        self.param_labels['risk'].configure(
            text=risk, text_color=color)

        # Timeline
        ts = datetime.datetime.now()\
            .strftime("%H:%M:%S")
        self.timeline.add_point(score, ts)

        # History bar
        self.score_history.append(score)
        if len(self.score_history) > 60:
            self.score_history.pop(0)
        self._draw_history()

    # ─────────────────────────────────────────────────
    # ACTIVITY LOG
    # ─────────────────────────────────────────────────
    def _add_activity(self, text, color=C_GREEN):
        ts = datetime.datetime.now()\
            .strftime("%H:%M:%S")
        self.activity_log.insert(0, (ts, text, color))
        if len(self.activity_log) > 8:
            self.activity_log.pop()
        self._rebuild_activity()

    def _rebuild_activity(self):
        for w in self.activity_frame.winfo_children():
            w.destroy()
        for ts, text, color in self.activity_log[:6]:
            row = ctk.CTkFrame(
                self.activity_frame,
                fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="●",
                font=("JetBrains Mono", 8),
                text_color=color
            ).pack(side="left")
            ctk.CTkLabel(row, text=ts,
                font=("JetBrains Mono", 9),
                text_color="#555568",
                width=72
            ).pack(side="left", padx=(6, 10))
            ctk.CTkLabel(row, text=text,
                font=("Syne", 11),
                text_color=C_BRIGHT
            ).pack(side="left")

    # ─────────────────────────────────────────────────
    # INTRUSION LOG
    # ─────────────────────────────────────────────────
    def _add_intrusion(self, entry):
        self.log_box.configure(state="normal")
        line = (
            f"[{entry['time']}]  "
            f"score={entry['score']:.1f}  "
            f"risk={entry['risk']}  "
            f"dwell={entry['dwell']:.0f}ms  "
            f"flight={entry['flight']:.0f}ms\n"
        )
        self.log_box.insert("0.0", line,
                            entry['risk'])
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")
        self.intrusion_log.clear()

    def _focus_log(self):
        """Scroll to security log section."""
        pass

    # ─────────────────────────────────────────────────
    # SCORE HISTORY BAR
    # ─────────────────────────────────────────────────
    def _draw_history(self):
        c = self.bar_canvas
        c.delete("all")
        w = c.winfo_width()
        h = 40
        n = len(self.score_history)
        if n < 2 or w < 10:
            return
        bw = w / n
        for i, s in enumerate(self.score_history):
            col = (C_GREEN  if s >= 68
                   else C_AMBER if s >= 52
                   else C_RED)
            bh = max(3, int(s/100*(h-6)))+3
            c.create_rectangle(
                i*bw+1, h-bh,
                (i+1)*bw-1, h,
                fill=col, outline="")