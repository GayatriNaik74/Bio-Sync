"""
BioSync — ui/enrollment.py
3 sessions × 2 minutes. Records keystrokes, trains model inline,
then auto-navigates to dashboard.
"""

import customtkinter as ctk
import tkinter as tk
import threading, time, os, csv, datetime
import json, glob, sys, numpy as np, joblib
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', 'src'))
from features import (load_events, compute_dwell,
                      compute_flight, extract_features)

# ── Paragraphs ───────────────────────────────────────
PARAGRAPHS = [
    "Authentication systems verify user identity through behavioral patterns and biometric signals. Keystroke dynamics capture the unique rhythm of each individual typing on a keyboard device naturally.",
    "Machine learning models analyse timing intervals between consecutive keystrokes to detect anomalies. Continuous authentication ensures security without interrupting the natural workflow of any user.",
    "Neural networks trained on typing patterns can distinguish between authorised users and potential intruders. The dwell time and flight time features form the core of behavioral biometric authentication systems.",
]

USERS_FILE   = "data/users.json"
RAW_DIR      = "data/raw"
SCALER_PATH  = "models/pretrained_scaler.pkl"
BASELINE_OUT = "models/user_baseline.pkl"
SESSION_SECS = 120

C_BG     = "#07070b"
C_CARD   = "#0d0d16"
C_BORDER = "#1c1c28"
C_DIM    = "#2e2e44"
C_BRIGHT = "#d4d4f0"
C_PURPLE = "#a78bfa"
C_GREEN  = "#4ade80"
C_AMBER  = "#fbbf24"
C_RED    = "#f87171"
C_CURSOR = "#a78bfa"
C_PENDING= "#2e2e44"


class EnrollmentScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color=C_BG)
        self.app            = app
        self.state          = state
        self.current_step   = 0
        self.total_steps    = 3
        self.para_text      = ""
        self.typed_pos      = 0
        self.events         = []
        self.timer_val      = SESSION_SECS
        self.timer_id       = None
        self.session_active = False
        self.press_times    = {}
        self.last_press     = None
        self.wrong_count    = 0
        self.correct_count  = 0
        self._build()

    # ─────────────────────────────────────────────────
    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#0a0a12",
                           height=56, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🛡  BioSync",
            font=("Syne", 13, "bold"),
            text_color="#60a5fa"
        ).pack(side="left", padx=24)
        ctk.CTkLabel(hdr,
            text="ENROLLMENT  ·  3 sessions × 2 min",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(side="right", padx=24)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(expand=True, fill="both",
                  padx=56, pady=24)

        # Title + dots
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(top,
            text="Build Your Typing Profile",
            font=("Syne", 22, "bold"),
            text_color=C_BRIGHT
        ).pack(side="left")

        dots_f = ctk.CTkFrame(top, fg_color="transparent")
        dots_f.pack(side="right")
        self.step_dots = []
        for i in range(3):
            f = ctk.CTkFrame(dots_f,
                             fg_color="transparent")
            f.pack(side="left", padx=10)
            dot = ctk.CTkLabel(f, text="○",
                font=("JetBrains Mono", 20),
                text_color=C_DIM)
            dot.pack()
            lbl = ctk.CTkLabel(f, text=f"S{i+1}",
                font=("JetBrains Mono", 9),
                text_color=C_DIM)
            lbl.pack()
            self.step_dots.append((dot, lbl))

        # Stats row
        stats = ctk.CTkFrame(body,
            fg_color=C_CARD, corner_radius=10,
            border_width=1, border_color=C_BORDER)
        stats.pack(fill="x", pady=(0, 14))
        self.stat_labels = {}
        for col, (icon, key, default) in enumerate([
            ("⏱", "timer",    "2:00"),
            ("⌨", "keys",     "0"),
            ("✓", "accuracy", "—"),
            ("📈","progress",  "0 / 3"),
        ]):
            cell = ctk.CTkFrame(stats,
                                fg_color="transparent")
            cell.grid(row=0, column=col,
                      padx=20, pady=12, sticky="w")
            ctk.CTkLabel(cell, text=icon,
                font=("Segoe UI Emoji", 12),
                text_color=C_DIM
            ).pack(side="left", padx=(0, 6))
            lbl = ctk.CTkLabel(cell, text=default,
                font=("JetBrains Mono", 14, "bold"),
                text_color=C_BRIGHT)
            lbl.pack(side="left")
            self.stat_labels[key] = lbl
        stats.grid_columnconfigure((0,1,2,3), weight=1)

        # Timer bar
        self.timer_bar = ctk.CTkProgressBar(body,
            fg_color="#111120",
            progress_color=C_PURPLE,
            height=5, corner_radius=3)
        self.timer_bar.pack(fill="x", pady=(0, 14))
        self.timer_bar.set(1.0)

        # Paragraph display
        para_card = ctk.CTkFrame(body,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        para_card.pack(fill="x", pady=(0, 12))
        top_para = ctk.CTkFrame(para_card,
                                fg_color="transparent")
        top_para.pack(fill="x", padx=20,
                      pady=(14, 4))
        ctk.CTkLabel(top_para,
            text="TYPE THIS PARAGRAPH",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(side="left")
        self.para_counter = ctk.CTkLabel(top_para,
            text="0 / 0 chars",
            font=("JetBrains Mono", 9),
            text_color=C_DIM)
        self.para_counter.pack(side="right")

        self.para_display = tk.Text(para_card,
            height=4, wrap="word",
            bg=C_CARD, fg=C_PENDING,
            font=("JetBrains Mono", 12),
            relief="flat", bd=0,
            selectbackground=C_CARD,
            highlightthickness=0,
            state="disabled",
            padx=20, pady=8,
            cursor="arrow",
            spacing1=2, spacing2=4)
        self.para_display.pack(
            fill="x", padx=4, pady=(0, 14))
        self.para_display.tag_config(
            "correct", foreground=C_GREEN)
        self.para_display.tag_config(
            "wrong",   foreground=C_RED,
            background="#1a0a0a")
        self.para_display.tag_config(
            "cursor",  foreground=C_CURSOR,
            underline=True)
        self.para_display.tag_config(
            "pending", foreground=C_PENDING)

        # Input
        input_card = ctk.CTkFrame(body,
            fg_color=C_CARD, corner_radius=12,
            border_width=1, border_color=C_BORDER)
        input_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(input_card,
            text="YOUR INPUT",
            font=("JetBrains Mono", 9),
            text_color=C_DIM, anchor="w"
        ).pack(padx=20, pady=(14, 6), anchor="w")
        self.type_entry = ctk.CTkEntry(input_card,
            placeholder_text="Press Start Session...",
            height=44, corner_radius=8,
            fg_color="#0a0a12",
            border_color=C_BORDER,
            text_color=C_BRIGHT,
            placeholder_text_color=C_DIM,
            font=("JetBrains Mono", 13),
            state="disabled")
        self.type_entry.pack(
            fill="x", padx=16, pady=(0, 16))
        self.type_entry.bind("<KeyPress>",
                             self._on_keypress)
        self.type_entry.bind("<KeyRelease>",
                             self._on_keyrelease)

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(body,
            fg_color="#111120",
            progress_color=C_GREEN,
            height=4, corner_radius=3)
        self.prog_bar.pack(fill="x", pady=(0, 10))
        self.prog_bar.set(0)

        # Status
        self.status_lbl = ctk.CTkLabel(body,
            text="3 sessions × 2 minutes  ·  "
                 "type naturally, don't rush",
            font=("JetBrains Mono", 10),
            text_color=C_DIM)
        self.status_lbl.pack(pady=(0, 12))

        # Start button
        self.start_btn = ctk.CTkButton(body,
            text="▶   Start Session 1",
            height=46, corner_radius=10,
            fg_color=C_PURPLE,
            hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 14, "bold"),
            command=self._start_session)
        self.start_btn.pack(fill="x")

    # ─────────────────────────────────────────────────
    def on_show(self):
        self.current_step   = 0
        self.typed_pos      = 0
        self.session_active = False
        if self.timer_id:
            self.after_cancel(self.timer_id)
        self.prog_bar.set(0)
        self.timer_bar.set(1.0)
        self.timer_bar.configure(
            progress_color=C_PURPLE)
        for dot, lbl in self.step_dots:
            dot.configure(text="○", text_color=C_DIM)
            lbl.configure(text_color=C_DIM)
        self.stat_labels['timer'].configure(
            text="2:00", text_color=C_BRIGHT)
        self.stat_labels['keys'].configure(text="0")
        self.stat_labels['accuracy'].configure(text="—")
        self.stat_labels['progress'].configure(
            text=f"0 / {self.total_steps}")
        self.para_counter.configure(text="0 / 0 chars")
        self.para_display.configure(state="normal")
        self.para_display.delete("1.0", "end")
        self.para_display.configure(state="disabled")
        self.type_entry.configure(
            state="disabled", border_color=C_BORDER,
            placeholder_text="Press Start Session...")
        self.start_btn.configure(
            state="normal",
            text="▶   Start Session 1",
            fg_color=C_PURPLE, text_color="#07070b")
        self._update_status(
            "3 sessions × 2 minutes  ·  "
            "type naturally, don't rush", C_DIM)
        # Pre-load first paragraph
        self.para_text = PARAGRAPHS[0]
        self._render_para()
        self.para_counter.configure(
            text=f"0 / {len(self.para_text)} chars")

    # ─────────────────────────────────────────────────
    def _start_session(self):
        self.para_text      = PARAGRAPHS[self.current_step]
        self.typed_pos      = 0
        self.events         = []
        self.timer_val      = SESSION_SECS
        self.session_active = True
        self.press_times    = {}
        self.last_press     = None
        self.wrong_count    = 0
        self.correct_count  = 0

        dot, lbl = self.step_dots[self.current_step]
        dot.configure(text="◉", text_color=C_AMBER)
        lbl.configure(text_color=C_AMBER)

        self._render_para()
        self.para_counter.configure(
            text=f"0 / {len(self.para_text)} chars")
        self.stat_labels['timer'].configure(
            text="2:00", text_color=C_BRIGHT)
        self.stat_labels['keys'].configure(text="0")
        self.stat_labels['accuracy'].configure(
            text="100%", text_color=C_GREEN)
        self.stat_labels['progress'].configure(
            text=f"{self.current_step} / "
                 f"{self.total_steps}")
        self.timer_bar.configure(
            progress_color=C_PURPLE)
        self.timer_bar.set(1.0)
        self.type_entry.configure(
            state="normal",
            placeholder_text="start typing now...",
            border_color=C_PURPLE)
        self.type_entry.delete(0, "end")
        self.type_entry.focus()
        self.start_btn.configure(
            state="disabled",
            text="● Recording...",
            fg_color="#1a0a1a",
            text_color=C_PURPLE)
        self._update_status(
            f"Session {self.current_step+1} — "
            "type the paragraph. Loops if done early.",
            C_AMBER)
        self._tick()

    def _tick(self):
        if not self.session_active:
            return
        self.timer_val -= 1
        remaining = self.timer_val
        mins = remaining // 60
        secs = remaining % 60
        color = (C_GREEN  if remaining > 60
                 else C_AMBER if remaining > 30
                 else C_RED)
        bar_c = (C_PURPLE if remaining > 60
                 else C_AMBER if remaining > 30
                 else C_RED)
        self.stat_labels['timer'].configure(
            text=f"{mins}:{secs:02d}",
            text_color=color)
        self.timer_bar.configure(progress_color=bar_c)
        self.timer_bar.set(remaining / SESSION_SECS)
        if remaining <= 15:
            bc = (C_RED if remaining % 2 == 0
                  else C_BORDER)
            self.type_entry.configure(
                border_color=bc)
        if remaining <= 0:
            self._end_session()
        else:
            self.timer_id = self.after(
                1000, self._tick)

    def _end_session(self):
        self.session_active = False
        if self.timer_id:
            self.after_cancel(self.timer_id)
        self.type_entry.configure(
            state="disabled",
            border_color=C_BORDER)
        self.timer_bar.set(0)
        self.stat_labels['timer'].configure(
            text="0:00", text_color=C_DIM)
        self._save_session()
        dot, lbl = self.step_dots[self.current_step]
        dot.configure(text="●", text_color=C_GREEN)
        lbl.configure(text_color=C_GREEN)
        self.current_step += 1
        prog = self.current_step / self.total_steps
        self.prog_bar.set(prog)
        self.stat_labels['progress'].configure(
            text=f"{self.current_step} / "
                 f"{self.total_steps}")
        if self.current_step >= self.total_steps:
            self._update_status(
                "✓  All 3 sessions done! "
                "Training your model...", C_GREEN)
            self.start_btn.configure(
                state="disabled",
                text="⏳  Training model...",
                fg_color="#0d0d16",
                text_color=C_DIM)
            self.after(600, self._train_inline)
        else:
            self._update_status(
                f"✓  Session {self.current_step} "
                f"saved ({len(self.events)} keys)  —  "
                f"start session "
                f"{self.current_step+1} when ready.",
                C_GREEN)
            self.start_btn.configure(
                state="normal",
                text=f"▶   Start Session "
                     f"{self.current_step+1}",
                fg_color=C_PURPLE,
                text_color="#07070b")

    # ─────────────────────────────────────────────────
    def _on_keypress(self, event):
        if not self.session_active:
            return
        now_ms = int(time.time() * 1000)
        if event.keysym in (
            "Shift_L","Shift_R","Control_L",
            "Control_R","Alt_L","Alt_R",
            "BackSpace","Return","Tab","Escape",
            "Delete","Left","Right","Up","Down",
            "Home","End","Prior","Next","Insert",
            "F1","F2","F3","F4","F5","F6","F7",
            "F8","F9","F10","F11","F12"):
            return
        key = event.char
        if not key or not key.isprintable():
            return
        flight = ((now_ms - self.last_press)
                  if self.last_press else 0)
        self.last_press   = now_ms
        self.press_times[key] = now_ms
        self.events.append({
            "timestamp_ms": now_ms,
            "key":          key,
            "event_type":   "press",
            "flight_ms":    flight,
        })
        if self.typed_pos < len(self.para_text):
            expected = self.para_text[self.typed_pos]
            if key == expected:
                self.correct_count += 1
                self.typed_pos     += 1
                if self.typed_pos >= len(self.para_text):
                    self.typed_pos = 0
                    self._update_status(
                        "✓ Paragraph complete — "
                        "looping back, keep going!",
                        C_GREEN)
                    self.after(50, lambda:
                        self.type_entry.delete(0,"end"))
            else:
                self.wrong_count += 1
        total = self.correct_count + self.wrong_count
        acc   = int(self.correct_count / total * 100
                    ) if total else 100
        acc_c = (C_GREEN  if acc >= 90
                 else C_AMBER if acc >= 70
                 else C_RED)
        self.stat_labels['keys'].configure(
            text=str(total))
        self.stat_labels['accuracy'].configure(
            text=f"{acc}%", text_color=acc_c)
        self.para_counter.configure(
            text=f"{self.typed_pos} / "
                 f"{len(self.para_text)} chars")
        self._render_para()

    def _on_keyrelease(self, event):
        if not self.session_active:
            return
        now_ms  = int(time.time() * 1000)
        key     = event.char
        if not key or not key.isprintable():
            return
        press_t = self.press_times.pop(
            key, now_ms - 80)
        dwell   = now_ms - press_t
        for evt in reversed(self.events):
            if (evt["key"] == key and
                    "dwell_ms" not in evt):
                evt["dwell_ms"] = dwell
                break

    def _render_para(self):
        d    = self.para_display
        para = self.para_text
        pos  = self.typed_pos
        d.configure(state="normal")
        d.delete("1.0", "end")
        for i, ch in enumerate(para):
            tag = ("correct" if i < pos
                   else "cursor" if i == pos
                   else "pending")
            d.insert("end", ch, tag)
        d.configure(state="disabled")

    def _save_session(self):
        os.makedirs(RAW_DIR, exist_ok=True)
        ts   = datetime.datetime.now().strftime(
            "%Y%m%d_%H%M%S")
        path = os.path.join(
            RAW_DIR, f"session_{ts}.csv")
        with open(path, "w", newline="") as f:
            import csv as _csv
            w = _csv.DictWriter(f, fieldnames=[
                "timestamp_ms","key","event_type",
                "flight_ms","dwell_ms"])
            w.writeheader()
            for evt in self.events:
                w.writerow({
                    "timestamp_ms":
                        evt.get("timestamp_ms",""),
                    "key": evt.get("key",""),
                    "event_type":
                        evt.get("event_type","press"),
                    "flight_ms":
                        evt.get("flight_ms", 0),
                    "dwell_ms":
                        evt.get("dwell_ms",  0),
                })
        self._update_status(
            f"✓  Saved {len(self.events)} keystrokes"
            f" → {os.path.basename(path)}", C_GREEN)

    # ─────────────────────────────────────────────────
    # INLINE TRAINING — no subprocess
    # ─────────────────────────────────────────────────
    def _train_inline(self):
        def _thread():
            try:
                files = sorted(glob.glob(
                    os.path.join(RAW_DIR,
                                 "session_*.csv")))
                if not files:
                    raise FileNotFoundError(
                        "No session CSVs found")

                feature_rows = []
                for path in files:
                    try:
                        df        = load_events(path)
                        dwell_df  = compute_dwell(df)
                        flight_df = compute_flight(df)
                        if (len(dwell_df) < 5 or
                                len(flight_df) < 5):
                            continue
                        feat = extract_features(
                            dwell_df, flight_df)
                        feature_rows.append(
                            list(feat.values()))
                    except Exception:
                        continue

                if not feature_rows:
                    raise ValueError(
                        "No valid sessions")

                X_raw  = np.array(feature_rows)
                scaler = joblib.load(SCALER_PATH)
                n_cmu  = scaler.n_features_in_
                n_user = X_raw.shape[1]
                if n_user < n_cmu:
                    pad   = np.zeros((
                        X_raw.shape[0],
                        n_cmu - n_user))
                    X_pad = np.hstack([X_raw, pad])
                else:
                    X_pad = X_raw[:, :n_cmu]
                X_scaled = scaler.transform(X_pad)

                model = IsolationForest(
                    n_estimators=300,
                    contamination=0.1,
                    random_state=42,
                    n_jobs=-1)
                model.fit(X_scaled)
                scores = model.decision_function(
                    X_scaled)

                baseline = {
                    'model'      : model,
                    'scaler'     : scaler,
                    'mean_score' : float(scores.mean()),
                    'std_score'  : float(scores.std()),
                    'threshold'  : float(
                        scores.mean() -
                        2 * scores.std()),
                    'n_sessions' : X_raw.shape[0],
                    'feat_mean'  :
                        X_raw.mean(axis=0).tolist(),
                    'feat_std'   :
                        X_raw.std(axis=0).tolist(),
                }
                os.makedirs("models", exist_ok=True)
                joblib.dump(baseline, BASELINE_OUT)

                # Mark enrolled
                if os.path.exists(USERS_FILE):
                    with open(USERS_FILE) as f:
                        users = json.load(f)
                    uname = self.state.get("username")
                    if uname and uname in users:
                        users[uname]["enrolled"] = True
                        with open(USERS_FILE,"w") as f:
                            json.dump(users, f,
                                      indent=2)
                self.state["enrolled"] = True
                self.after(0, lambda: self._update_status(
                    "✓  Model trained! "
                    "Launching dashboard...",
                    C_GREEN))
                self.after(1200, lambda:
                    self.app.show_screen("dashboard"))

            except Exception as e:
                self.after(0, lambda:
                    self._update_status(
                        f"Error: {e}", C_RED))

        threading.Thread(
            target=_thread, daemon=True).start()

    def _update_status(self, text, color=None):
        kw = {"text": text}
        if color:
            kw["text_color"] = color
        self.status_lbl.configure(**kw)