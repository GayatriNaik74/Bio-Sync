"""
BioSync — ui/admin_dashboard.py
Admin dashboard showing all users, their sessions,
intrusion events, and live status.
Polls admin_logs.json every 10 seconds.
"""

import sys, os
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', 'src'))

import customtkinter as ctk
import tkinter as tk
import datetime, threading, json

from admin_logger import (
    get_all_logs,
    get_user_summary,
    export_user_csv,
    export_summary_csv,
)

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
C_GREY   = "#6b7280"

POLL_INTERVAL = 10000   # 10 seconds


class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color=C_BG)
        self.app              = app
        self.state            = state
        self.selected_user    = None
        self.user_buttons     = {}
        self._poll_id         = None
        self._build()

    # ─────────────────────────────────────────────────
    def on_show(self):
        self.selected_user = None
        self._refresh()
        self._start_polling()

    def on_hide(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)

    # ─────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────
    def _build(self):

        # ── TOP BAR ──────────────────────────────────
        top = ctk.CTkFrame(self, height=54,
            fg_color="#0a0a12", corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top,
            text="🛡  BioSync  Admin",
            font=("Syne", 14, "bold"),
            text_color=C_BLUE
        ).pack(side="left", padx=20)

        ctk.CTkButton(top,
            text="⏻  Logout",
            width=90, height=30,
            fg_color="transparent",
            hover_color="#1a0a0a",
            text_color=C_RED,
            font=("Syne", 11),
            corner_radius=6,
            command=self._logout
        ).pack(side="right", padx=16)

        ctk.CTkButton(top,
            text="⬇  Export All",
            width=110, height=30,
            fg_color="transparent",
            hover_color="#1e3a5f",
            text_color=C_BLUE,
            font=("Syne", 11),
            corner_radius=6,
            command=self._export_all
        ).pack(side="right", padx=4)

        # Last refreshed label
        self.refresh_lbl = ctk.CTkLabel(top,
            text="",
            font=("JetBrains Mono", 9),
            text_color=C_DIM)
        self.refresh_lbl.pack(
            side="right", padx=16)

        # ── SUMMARY STRIP ─────────────────────────────
        strip = ctk.CTkFrame(self, height=48,
            fg_color=C_CARD, corner_radius=0)
        strip.pack(fill="x")
        strip.pack_propagate(False)

        self.stat_labels = {}
        for key, label, color in [
            ("total_users",   "Total Users",      C_BRIGHT),
            ("active_users",  "Active Sessions",  C_GREEN),
            ("locked_users",  "Currently Locked", C_RED),
            ("intrusions_today","Intrusions Today",C_AMBER),
        ]:
            cell = ctk.CTkFrame(strip,
                fg_color="transparent")
            cell.pack(side="left",
                      padx=28, pady=8)
            ctk.CTkLabel(cell, text=label,
                font=("JetBrains Mono", 9),
                text_color=C_DIM
            ).pack()
            lbl = ctk.CTkLabel(cell, text="—",
                font=("Syne", 15, "bold"),
                text_color=color)
            lbl.pack()
            self.stat_labels[key] = lbl

        # ── MAIN AREA ─────────────────────────────────
        body = ctk.CTkFrame(self,
                            fg_color="transparent")
        body.pack(fill="both", expand=True)

        # ── LEFT — User list ──────────────────────────
        left = ctk.CTkFrame(body, width=240,
            fg_color=C_SIDE, corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ctk.CTkLabel(left,
            text="ALL USERS",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(pady=(14, 6), padx=14, anchor="w")

        self.user_list_frame = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color="#1e1e2a")
        self.user_list_frame.pack(
            fill="both", expand=True,
            padx=8, pady=(0, 8))

        # Export selected user button
        ctk.CTkButton(left,
            text="⬇  Export User CSV",
            height=32, anchor="w",
            fg_color="transparent",
            hover_color="#1e3a5f",
            text_color=C_DIM,
            font=("JetBrains Mono", 9),
            corner_radius=6,
            command=self._export_user
        ).pack(fill="x", padx=8,
               pady=(0, 8))

        # ── RIGHT — Detail panel ──────────────────────
        right = ctk.CTkFrame(body,
            fg_color="transparent")
        right.pack(side="left", fill="both",
                   expand=True)

        # User detail header
        self.detail_header = ctk.CTkFrame(right,
            fg_color=C_CARD, corner_radius=0,
            height=54)
        self.detail_header.pack(fill="x")
        self.detail_header.pack_propagate(False)

        self.selected_lbl = ctk.CTkLabel(
            self.detail_header,
            text="← Select a user from the list",
            font=("Syne", 13, "bold"),
            text_color=C_DIM)
        self.selected_lbl.pack(
            side="left", padx=20)

        self.user_status_lbl = ctk.CTkLabel(
            self.detail_header,
            text="",
            font=("JetBrains Mono", 10),
            text_color=C_DIM)
        self.user_status_lbl.pack(
            side="right", padx=20)

        # User stats cards
        self.user_stats_frame = ctk.CTkFrame(
            right, fg_color="transparent",
            height=80)
        self.user_stats_frame.pack(
            fill="x", padx=16, pady=10)

        self.user_stat_labels = {}
        for key, label, color in [
            ("enrolled_on",      "Enrolled On",      C_DIM),
            ("last_seen",        "Last Seen",        C_DIM),
            ("total_events",     "Total Events",     C_BRIGHT),
            ("total_locks",      "Total Locks",      C_RED),
            ("intrusions_today", "Intrusions Today", C_AMBER),
            ("last_score",       "Last Score",       C_GREEN),
        ]:
            card = ctk.CTkFrame(
                self.user_stats_frame,
                fg_color=C_CARD,
                corner_radius=8,
                border_width=1,
                border_color=C_BORDER)
            card.pack(side="left",
                      padx=4, pady=4,
                      expand=True, fill="both")
            ctk.CTkLabel(card, text=label,
                font=("JetBrains Mono", 8),
                text_color=C_DIM
            ).pack(padx=10, pady=(8, 2))
            lbl = ctk.CTkLabel(card, text="—",
                font=("Syne", 13, "bold"),
                text_color=color)
            lbl.pack(padx=10, pady=(0, 8))
            self.user_stat_labels[key] = lbl

        # Intrusion log header
        log_hdr = ctk.CTkFrame(right,
            fg_color="transparent")
        log_hdr.pack(fill="x",
                     padx=16, pady=(4, 4))
        ctk.CTkLabel(log_hdr,
            text="INTRUSION / ANOMALY LOG",
            font=("JetBrains Mono", 9),
            text_color=C_DIM
        ).pack(side="left")
        ctk.CTkLabel(log_hdr,
            text="showing last 200 events",
            font=("JetBrains Mono", 8),
            text_color="#1e1e2a"
        ).pack(side="right")

        # Log table header
        hdr = ctk.CTkFrame(right,
            fg_color="#111118",
            corner_radius=0)
        hdr.pack(fill="x", padx=16)
        for col_txt, width in [
            ("Timestamp",  160),
            ("Score",       60),
            ("Risk",        70),
            ("Dwell ms",    72),
            ("Flight ms",   72),
            ("Mouse px/s",  80),
            ("Locked",      60),
            ("TX Hash",    120),
        ]:
            ctk.CTkLabel(hdr, text=col_txt,
                width=width,
                font=("JetBrains Mono", 9),
                text_color=C_DIM,
                anchor="w"
            ).pack(side="left",
                   padx=(8, 0), pady=6)

        # Log rows — scrollable
        self.log_frame = ctk.CTkScrollableFrame(
            right,
            fg_color=C_CARD,
            corner_radius=0,
            scrollbar_button_color="#1e1e2a")
        self.log_frame.pack(
            fill="both", expand=True,
            padx=16, pady=(0, 8))

    # ─────────────────────────────────────────────────
    # REFRESH
    # ─────────────────────────────────────────────────
    def _refresh(self):
        """Reload all data from admin_logs.json."""
        logs = get_all_logs()
        self._update_summary(logs)
        self._update_user_list(logs)
        if self.selected_user:
            self._show_user_detail(
                self.selected_user)
        now = datetime.datetime.now()\
            .strftime("%H:%M:%S")
        self.refresh_lbl.configure(
            text=f"Updated {now}")

    def _start_polling(self):
        """Poll every 10 seconds."""
        def _poll():
            if not self.winfo_exists():
                return
            self._refresh()
            self._poll_id = self.after(
                POLL_INTERVAL, _poll)
        self._poll_id = self.after(
            POLL_INTERVAL, _poll)

    # ─────────────────────────────────────────────────
    # SUMMARY STRIP
    # ─────────────────────────────────────────────────
    def _update_summary(self, logs: dict):
        today = datetime.date.today().strftime(
            "%Y-%m-%d")
        total     = len(logs)
        active    = 0
        locked    = 0
        intrusions= 0

        for uname, udata in logs.items():
            events = udata.get("events", [])
            if events:
                last  = events[0]
                ts    = last.get("timestamp", "")
                score = last.get("score", 100)
                risk  = last.get("risk", "LOW")
                # Active if last event within 5 min
                try:
                    last_dt = datetime.datetime\
                        .strptime(ts,
                            "%Y-%m-%d %H:%M:%S")
                    diff = (datetime.datetime.now()
                            - last_dt).total_seconds()
                    if diff < 300:
                        active += 1
                        if risk == "HIGH":
                            locked += 1
                except Exception:
                    pass
            intrusions += sum(
                1 for e in events
                if e.get("risk") in
                ("MEDIUM", "HIGH") and
                e.get("timestamp", ""
                      ).startswith(today))

        self.stat_labels["total_users"]\
            .configure(text=str(total))
        self.stat_labels["active_users"]\
            .configure(text=str(active))
        self.stat_labels["locked_users"]\
            .configure(text=str(locked))
        self.stat_labels["intrusions_today"]\
            .configure(text=str(intrusions))

    # ─────────────────────────────────────────────────
    # USER LIST
    # ─────────────────────────────────────────────────
    def _update_user_list(self, logs: dict):
        for w in self.user_list_frame\
                .winfo_children():
            w.destroy()
        self.user_buttons = {}

        if not logs:
            ctk.CTkLabel(
                self.user_list_frame,
                text="No users enrolled yet",
                font=("JetBrains Mono", 10),
                text_color=C_DIM
            ).pack(pady=20)
            return

        for uname, udata in logs.items():
            events = udata.get("events", [])
            status_color, status_dot = \
                self._get_status(events)

            btn_frame = ctk.CTkFrame(
                self.user_list_frame,
                fg_color=(
                    "#1e3a5f"
                    if uname == self.selected_user
                    else "transparent"),
                corner_radius=8)
            btn_frame.pack(
                fill="x", pady=2)

            # Status dot
            ctk.CTkLabel(btn_frame,
                text=status_dot,
                font=("JetBrains Mono", 14),
                text_color=status_color
            ).pack(side="left", padx=(10, 6),
                   pady=8)

            # Name + last score
            info = ctk.CTkFrame(btn_frame,
                fg_color="transparent")
            info.pack(side="left",
                      fill="x", expand=True)
            ctk.CTkLabel(info, text=uname,
                font=("Syne", 12),
                text_color=C_BRIGHT,
                anchor="w"
            ).pack(anchor="w")

            last_score = "—"
            last_risk  = "—"
            if events:
                last_score = str(
                    events[0].get("score", "—"))
                last_risk  = events[0].get(
                    "risk", "—")
            ctk.CTkLabel(info,
                text=f"score={last_score}  "
                     f"risk={last_risk}",
                font=("JetBrains Mono", 8),
                text_color=C_DIM,
                anchor="w"
            ).pack(anchor="w")

            btn_frame.bind("<Button-1>",
                lambda e, u=uname:
                    self._select_user(u))
            for child in btn_frame.winfo_children():
                child.bind("<Button-1>",
                    lambda e, u=uname:
                        self._select_user(u))

            self.user_buttons[uname] = btn_frame

    def _get_status(self, events):
        """Return (color, dot) for user status."""
        if not events:
            return C_GREY, "○"
        last = events[0]
        ts   = last.get("timestamp", "")
        risk = last.get("risk", "LOW")
        try:
            last_dt = datetime.datetime.strptime(
                ts, "%Y-%m-%d %H:%M:%S")
            diff = (datetime.datetime.now()
                    - last_dt).total_seconds()
            if diff > 300:
                return C_GREY, "○"   # offline
        except Exception:
            return C_GREY, "○"

        if risk == "HIGH":
            return C_RED,   "●"   # locked
        elif risk == "MEDIUM":
            return C_AMBER, "●"   # warning
        else:
            return C_GREEN, "●"   # active

    # ─────────────────────────────────────────────────
    # USER DETAIL
    # ─────────────────────────────────────────────────
    def _select_user(self, username: str):
        self.selected_user = username
        # Refresh user list to highlight selection
        logs = get_all_logs()
        self._update_user_list(logs)
        self._show_user_detail(username)

    def _show_user_detail(self, username: str):
        logs    = get_all_logs()
        summary = get_user_summary(username)
        udata   = logs.get(username, {})
        events  = udata.get("events", [])

        # Header
        status_color, status_dot = \
            self._get_status(events)
        self.selected_lbl.configure(
            text=f"  {status_dot}  {username}",
            text_color=status_color)

        last_ts = summary.get("last_seen", "—")
        self.user_status_lbl.configure(
            text=f"Last active: {last_ts}")

        # Stats cards
        self.user_stat_labels["enrolled_on"]\
            .configure(
                text=summary.get(
                    "enrolled_on", "—")[-16:])
        self.user_stat_labels["last_seen"]\
            .configure(
                text=summary.get(
                    "last_seen", "—")[-8:])
        self.user_stat_labels["total_events"]\
            .configure(
                text=str(summary.get(
                    "total_events", 0)))
        self.user_stat_labels["total_locks"]\
            .configure(
                text=str(summary.get(
                    "total_locks", 0)))
        self.user_stat_labels["intrusions_today"]\
            .configure(
                text=str(summary.get(
                    "intrusions_today", 0)))
        last_score = summary.get("last_score", "—")
        last_risk  = summary.get("last_risk", "—")
        score_color = {
            "LOW"   : C_GREEN,
            "MEDIUM": C_AMBER,
            "HIGH"  : C_RED,
        }.get(last_risk, C_DIM)
        self.user_stat_labels["last_score"]\
            .configure(
                text=str(last_score),
                text_color=score_color)

        # Log rows
        for w in self.log_frame.winfo_children():
            w.destroy()

        if not events:
            ctk.CTkLabel(self.log_frame,
                text="No events recorded yet",
                font=("JetBrains Mono", 10),
                text_color=C_DIM
            ).pack(pady=20)
            return

        for i, evt in enumerate(events[:200]):
            risk  = evt.get("risk", "LOW")
            locked= evt.get("locked", False)
            row_bg = (
                "#120808" if risk == "HIGH"
                else "#121000" if risk == "MEDIUM"
                else "transparent")
            risk_color = {
                "HIGH"  : C_RED,
                "MEDIUM": C_AMBER,
                "LOW"   : C_GREEN,
            }.get(risk, C_DIM)

            row = ctk.CTkFrame(self.log_frame,
                fg_color=row_bg,
                corner_radius=4)
            row.pack(fill="x", pady=1)

            values = [
                (evt.get("timestamp","—"),      160),
                (str(evt.get("score","—")),      60),
                (risk,                           70),
                (str(evt.get("dwell_ms","—")),   72),
                (str(evt.get("flight_ms","—")),  72),
                (str(evt.get("mouse_vel","—")),  80),
                ("YES" if locked else "no",      60),
                (str(evt.get("tx_hash","—")),   120),
            ]
            for j,(val,w) in enumerate(values):
                col = (risk_color if j == 2
                       else C_RED if (j == 6
                            and locked)
                       else C_BRIGHT)
                ctk.CTkLabel(row,
                    text=val,
                    width=w,
                    font=("JetBrains Mono", 9),
                    text_color=col,
                    anchor="w"
                ).pack(side="left",
                       padx=(8, 0), pady=5)

    # ─────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────
    def _export_user(self):
        if not self.selected_user:
            return
        fname = (f"biosync_"
                 f"{self.selected_user}_"
                 f"{datetime.date.today()}.csv")
        path  = os.path.join(
            os.path.expanduser("~"),
            "Desktop", fname)
        ok = export_user_csv(
            self.selected_user, path)
        if ok:
            self._show_toast(
                f"✓ Exported → Desktop/{fname}")
        else:
            self._show_toast(
                "⚠ No data to export")

    def _export_all(self):
        fname = (f"biosync_all_users_"
                 f"{datetime.date.today()}.csv")
        path  = os.path.join(
            os.path.expanduser("~"),
            "Desktop", fname)
        ok = export_summary_csv(path)
        if ok:
            self._show_toast(
                f"✓ Exported → Desktop/{fname}")
        else:
            self._show_toast(
                "⚠ No data to export")

    def _show_toast(self, msg: str):
        self.refresh_lbl.configure(
            text=msg, text_color=C_GREEN)
        self.after(3000, lambda:
            self.refresh_lbl.configure(
                text_color=C_DIM))

    # ─────────────────────────────────────────────────
    def _logout(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self.app.show_screen("login")