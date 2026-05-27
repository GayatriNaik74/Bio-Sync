"""
BioSync — ui/admin_dashboard.py
Enhanced Admin Dashboard:
  - Bigger fonts and better visibility
  - Live user status with accurate data
  - Blockchain audit log tab
  - Correct stats calculation
  - Export CSV for users and summary
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
 
# ── Colours ───────────────────────────────────────────
C_BG     = "#07070b"
C_CARD   = "#0d0d14"
C_SIDE   = "#0a0a10"
C_PANEL  = "#0f0f18"
C_BORDER = "#1e1e2a"
C_DIM    = "#3a3a55"
C_BRIGHT = "#d4d4f0"
C_PURPLE = "#a78bfa"
C_GREEN  = "#4ade80"
C_AMBER  = "#fbbf24"
C_RED    = "#f87171"
C_BLUE   = "#60a5fa"
C_GREY   = "#6b7280"
 
POLL_INTERVAL = 10000
 
 
# ── Blockchain log reader ─────────────────────────────
def _read_blockchain_logs() -> list:
    """
    Read blockchain transaction logs.
    Tries multiple sources:
    1. data/blockchain_log.json (if bridge writes here)
    2. data/admin_logs.json tx_hash fields
    """
    logs = []
 
    # Source 1 — dedicated blockchain log file
    bc_file = "data/blockchain_log.json"
    if os.path.exists(bc_file):
        try:
            with open(bc_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                logs.extend(data)
            elif isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        logs.extend(v)
        except Exception:
            pass
 
    # Source 2 — extract tx_hash from admin logs
    admin_logs = get_all_logs()
    for uname, udata in admin_logs.items():
        for evt in udata.get("events", []):
            tx = evt.get("tx_hash", "")
            if tx and tx != "" and tx != "—":
                logs.append({
                    "timestamp": evt.get(
                        "timestamp", "—"),
                    "username" : uname,
                    "score"    : evt.get(
                        "score", "—"),
                    "risk"     : evt.get(
                        "risk", "—"),
                    "locked"   : evt.get(
                        "locked", False),
                    "tx_hash"  : tx,
                    "session_id": evt.get(
                        "session_id", "—"),
                })
 
    # Sort by timestamp descending
    try:
        logs.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True)
    except Exception:
        pass
 
    return logs[:500]
 
 
class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color=C_BG)
        self.app           = app
        self.state         = state
        self.selected_user = None
        self._poll_id      = None
        self._current_tab  = "intrusion"
        self._build()
 
    # ─────────────────────────────────────────────────
    def on_show(self):
        self.selected_user = None
        self._refresh()
        self._start_polling()
 
    def on_hide(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
 
    # ─────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────
    def _build(self):
 
        # ── TOP BAR ──────────────────────────────────
        top = ctk.CTkFrame(self, height=60,
            fg_color="#0a0a12", corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)
 
        ctk.CTkLabel(top,
            text="🛡  BioSync  —  Admin Console",
            font=("Syne", 16, "bold"),
            text_color=C_BLUE
        ).pack(side="left", padx=24, pady=14)
 
        ctk.CTkButton(top,
            text="⏻  Logout",
            width=100, height=34,
            fg_color="transparent",
            hover_color="#1a0a0a",
            text_color=C_RED,
            font=("Syne", 12),
            corner_radius=6,
            command=self._logout
        ).pack(side="right", padx=16, pady=12)
 
        ctk.CTkButton(top,
            text="⬇  Export All",
            width=120, height=34,
            fg_color="transparent",
            hover_color="#1e3a5f",
            text_color=C_BLUE,
            font=("Syne", 12),
            border_width=1,
            border_color=C_BORDER,
            corner_radius=6,
            command=self._export_all
        ).pack(side="right", padx=4, pady=12)
 
        self.refresh_lbl = ctk.CTkLabel(top,
            text="",
            font=("JetBrains Mono", 10),
            text_color=C_DIM)
        self.refresh_lbl.pack(
            side="right", padx=16)
 
        # ── SUMMARY STRIP ─────────────────────────────
        strip = ctk.CTkFrame(self, height=80,
            fg_color=C_CARD, corner_radius=0)
        strip.pack(fill="x")
        strip.pack_propagate(False)
 
        self.stat_labels = {}
        stats_def = [
            ("total_users",
             "Total Users",      C_BRIGHT, "👥"),
            ("active_users",
             "Active Sessions",  C_GREEN,  "🟢"),
            ("locked_users",
             "Currently Locked", C_RED,    "🔴"),
            ("intrusions_today",
             "Intrusions Today", C_AMBER,  "⚠"),
            ("total_events",
             "Total Events",     C_BLUE,   "📊"),
        ]
        for key, label, color, icon in stats_def:
            cell = ctk.CTkFrame(strip,
                fg_color=C_PANEL,
                corner_radius=8)
            cell.pack(side="left",
                      padx=10, pady=10,
                      expand=True, fill="both")
 
            top_row = ctk.CTkFrame(cell,
                fg_color="transparent")
            top_row.pack(fill="x",
                         padx=10, pady=(8, 2))
            ctk.CTkLabel(top_row,
                text=icon,
                font=("Segoe UI Emoji", 14)
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(top_row,
                text=label,
                font=("JetBrains Mono", 10),
                text_color=C_DIM
            ).pack(side="left")
 
            lbl = ctk.CTkLabel(cell,
                text="—",
                font=("Syne", 22, "bold"),
                text_color=color)
            lbl.pack(padx=10, pady=(0, 8),
                     anchor="w")
            self.stat_labels[key] = lbl
 
        # ── MAIN BODY ─────────────────────────────────
        body = ctk.CTkFrame(self,
                            fg_color="transparent")
        body.pack(fill="both", expand=True)
 
        # ── LEFT — User list ──────────────────────────
        left = ctk.CTkFrame(body, width=260,
            fg_color=C_SIDE, corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
 
        ctk.CTkLabel(left,
            text="ALL USERS",
            font=("JetBrains Mono", 10,
                  "bold"),
            text_color=C_DIM
        ).pack(pady=(16, 6), padx=16, anchor="w")
 
        ctk.CTkFrame(left, height=1,
            fg_color=C_BORDER
        ).pack(fill="x", padx=12)
 
        self.user_list_frame = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color="#1e1e2a",
            scrollbar_button_hover_color="#2e2e44")
        self.user_list_frame.pack(
            fill="both", expand=True,
            padx=6, pady=(6, 4))
 
        ctk.CTkFrame(left, height=1,
            fg_color=C_BORDER
        ).pack(fill="x", padx=12)
 
        ctk.CTkButton(left,
            text="⬇  Export User CSV",
            height=34, anchor="w",
            fg_color="transparent",
            hover_color="#1e3a5f",
            text_color=C_DIM,
            font=("JetBrains Mono", 10),
            corner_radius=6,
            command=self._export_user
        ).pack(fill="x", padx=8, pady=8)
 
        # ── RIGHT — Detail panel ──────────────────────
        right = ctk.CTkFrame(body,
            fg_color="transparent")
        right.pack(side="left", fill="both",
                   expand=True)
 
        # Detail header bar
        self.detail_header = ctk.CTkFrame(right,
            fg_color=C_CARD,
            corner_radius=0, height=60)
        self.detail_header.pack(fill="x")
        self.detail_header.pack_propagate(False)
 
        self.selected_lbl = ctk.CTkLabel(
            self.detail_header,
            text="←  Select a user from the list",
            font=("Syne", 14, "bold"),
            text_color=C_DIM)
        self.selected_lbl.pack(
            side="left", padx=20)
 
        self.user_status_lbl = ctk.CTkLabel(
            self.detail_header,
            text="",
            font=("JetBrains Mono", 11),
            text_color=C_DIM)
        self.user_status_lbl.pack(
            side="right", padx=20)
 
        # User stats row
        stats_row = ctk.CTkFrame(right,
            fg_color="transparent", height=90)
        stats_row.pack(fill="x",
                       padx=12, pady=8)
        stats_row.pack_propagate(False)
 
        self.user_stat_labels = {}
        user_stats_def = [
            ("enrolled_on",
             "Enrolled On",      C_DIM),
            ("last_seen",
             "Last Seen",        C_DIM),
            ("total_events",
             "Total Events",     C_BRIGHT),
            ("total_locks",
             "Total Locks",      C_RED),
            ("intrusions_today",
             "Intrusions Today", C_AMBER),
            ("last_score",
             "Last Score",       C_GREEN),
        ]
        for key, label, color in user_stats_def:
            card = ctk.CTkFrame(stats_row,
                fg_color=C_CARD,
                corner_radius=8,
                border_width=1,
                border_color=C_BORDER)
            card.pack(side="left", padx=4,
                      expand=True, fill="both")
            ctk.CTkLabel(card, text=label,
                font=("JetBrains Mono", 9),
                text_color=C_DIM
            ).pack(padx=10, pady=(8, 2))
            lbl = ctk.CTkLabel(card, text="—",
                font=("Syne", 15, "bold"),
                text_color=color)
            lbl.pack(padx=10,
                     pady=(0, 8))
            self.user_stat_labels[key] = lbl
 
        # ── Tab bar ────────────────────────────────
        tab_bar = ctk.CTkFrame(right,
            fg_color=C_CARD,
            corner_radius=0, height=44)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
 
        self.tab_btns = {}
        for tab_key, tab_label in [
            ("intrusion", "📋  Intrusion Log"),
            ("blockchain", "⛓  Blockchain Audit"),
            ("summary",   "📊  Session Summary"),
        ]:
            btn = ctk.CTkButton(tab_bar,
                text=tab_label,
                height=36,
                width=180,
                fg_color=(C_BLUE
                    if tab_key == "intrusion"
                    else "transparent"),
                hover_color="#1e3a5f",
                text_color=("white"
                    if tab_key == "intrusion"
                    else C_DIM),
                font=("Syne", 12),
                corner_radius=6,
                command=lambda t=tab_key:
                    self._switch_tab(t))
            btn.pack(side="left",
                     padx=4, pady=4)
            self.tab_btns[tab_key] = btn
 
        # ── Content area ───────────────────────────
        self.content_area = ctk.CTkFrame(right,
            fg_color="transparent")
        self.content_area.pack(
            fill="both", expand=True,
            padx=12, pady=(4, 8))
 
        # Build all three panels
        self._build_intrusion_panel()
        self._build_blockchain_panel()
        self._build_summary_panel()
 
        # Show intrusion by default
        self._switch_tab("intrusion")
 
    # ─────────────────────────────────────────────────
    # INTRUSION LOG PANEL
    # ─────────────────────────────────────────────────
    def _build_intrusion_panel(self):
        self.intrusion_panel = ctk.CTkFrame(
            self.content_area,
            fg_color="transparent")
 
        # Table header
        hdr = ctk.CTkFrame(
            self.intrusion_panel,
            fg_color="#111118",
            corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
 
        cols = [
            ("Timestamp",  170),
            ("Score",       70),
            ("Risk",        80),
            ("Dwell ms",    80),
            ("Flight ms",   80),
            ("Mouse px/s",  90),
            ("Locked",      70),
            ("Session ID", 130),
        ]
        for col_txt, width in cols:
            ctk.CTkLabel(hdr,
                text=col_txt,
                width=width,
                font=("JetBrains Mono", 10,
                      "bold"),
                text_color=C_BLUE,
                anchor="w"
            ).pack(side="left",
                   padx=(10, 0), pady=8)
 
        # Scrollable rows
        self.intrusion_scroll = ctk.CTkScrollableFrame(
            self.intrusion_panel,
            fg_color=C_CARD,
            corner_radius=8,
            scrollbar_button_color="#1e1e2a",
            scrollbar_button_hover_color="#2e2e44")
        self.intrusion_scroll.pack(
            fill="both", expand=True)
 
    # ─────────────────────────────────────────────────
    # BLOCKCHAIN AUDIT PANEL
    # ─────────────────────────────────────────────────
    def _build_blockchain_panel(self):
        self.blockchain_panel = ctk.CTkFrame(
            self.content_area,
            fg_color="transparent")
 
        # Info bar
        info = ctk.CTkFrame(
            self.blockchain_panel,
            fg_color=C_CARD,
            corner_radius=8)
        info.pack(fill="x", pady=(0, 6))
 
        ctk.CTkLabel(info,
            text="⛓  Ethereum Blockchain Audit Log",
            font=("Syne", 13, "bold"),
            text_color=C_BLUE
        ).pack(side="left", padx=16, pady=10)
 
        self.bc_count_lbl = ctk.CTkLabel(info,
            text="0 transactions",
            font=("JetBrains Mono", 10),
            text_color=C_DIM)
        self.bc_count_lbl.pack(
            side="right", padx=16)
 
        ctk.CTkButton(info,
            text="↻ Refresh",
            width=90, height=28,
            fg_color="transparent",
            hover_color="#1e3a5f",
            text_color=C_BLUE,
            font=("JetBrains Mono", 10),
            border_width=1,
            border_color=C_BORDER,
            corner_radius=6,
            command=self._refresh_blockchain
        ).pack(side="right", padx=8, pady=8)
 
        # Table header
        bc_hdr = ctk.CTkFrame(
            self.blockchain_panel,
            fg_color="#111118",
            corner_radius=6)
        bc_hdr.pack(fill="x", pady=(0, 2))
 
        bc_cols = [
            ("Timestamp",   170),
            ("User",        100),
            ("Score",        70),
            ("Risk",         80),
            ("Locked",       70),
            ("Session ID",  130),
            ("TX Hash",     200),
        ]
        for col_txt, width in bc_cols:
            ctk.CTkLabel(bc_hdr,
                text=col_txt,
                width=width,
                font=("JetBrains Mono", 10,
                      "bold"),
                text_color=C_PURPLE,
                anchor="w"
            ).pack(side="left",
                   padx=(10, 0), pady=8)
 
        # Scrollable rows
        self.bc_scroll = ctk.CTkScrollableFrame(
            self.blockchain_panel,
            fg_color=C_CARD,
            corner_radius=8,
            scrollbar_button_color="#1e1e2a",
            scrollbar_button_hover_color="#2e2e44")
        self.bc_scroll.pack(
            fill="both", expand=True)
 
    # ─────────────────────────────────────────────────
    # SESSION SUMMARY PANEL
    # ─────────────────────────────────────────────────
    def _build_summary_panel(self):
        self.summary_panel = ctk.CTkFrame(
            self.content_area,
            fg_color="transparent")
 
        # Header
        hdr = ctk.CTkFrame(
            self.summary_panel,
            fg_color=C_CARD,
            corner_radius=8)
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(hdr,
            text="📊  All Users Session Summary",
            font=("Syne", 13, "bold"),
            text_color=C_GREEN
        ).pack(side="left", padx=16, pady=10)
 
        # Table header
        sum_hdr = ctk.CTkFrame(
            self.summary_panel,
            fg_color="#111118",
            corner_radius=6)
        sum_hdr.pack(fill="x", pady=(0, 2))
 
        sum_cols = [
            ("Username",         130),
            ("Enrolled On",      160),
            ("Last Seen",        160),
            ("Total Events",     110),
            ("Total Locks",      100),
            ("Intrusions Today", 140),
            ("Last Score",       100),
            ("Last Risk",        100),
        ]
        for col_txt, width in sum_cols:
            ctk.CTkLabel(sum_hdr,
                text=col_txt,
                width=width,
                font=("JetBrains Mono", 10,
                      "bold"),
                text_color=C_GREEN,
                anchor="w"
            ).pack(side="left",
                   padx=(10, 0), pady=8)
 
        # Scrollable rows
        self.summary_scroll = ctk.CTkScrollableFrame(
            self.summary_panel,
            fg_color=C_CARD,
            corner_radius=8,
            scrollbar_button_color="#1e1e2a",
            scrollbar_button_hover_color="#2e2e44")
        self.summary_scroll.pack(
            fill="both", expand=True)
 
    # ─────────────────────────────────────────────────
    # TAB SWITCHING
    # ─────────────────────────────────────────────────
    def _switch_tab(self, tab: str):
        self._current_tab = tab
 
        # Update button styles
        for key, btn in self.tab_btns.items():
            if key == tab:
                btn.configure(
                    fg_color=C_BLUE,
                    text_color="white")
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=C_DIM)
 
        # Hide all panels
        self.intrusion_panel.pack_forget()
        self.blockchain_panel.pack_forget()
        self.summary_panel.pack_forget()
 
        # Show selected
        if tab == "intrusion":
            self.intrusion_panel.pack(
                fill="both", expand=True)
        elif tab == "blockchain":
            self.blockchain_panel.pack(
                fill="both", expand=True)
            self._refresh_blockchain()
        elif tab == "summary":
            self.summary_panel.pack(
                fill="both", expand=True)
            self._refresh_summary()
 
    # ─────────────────────────────────────────────────
    # REFRESH
    # ─────────────────────────────────────────────────
    def _refresh(self):
        logs = get_all_logs()
        self._update_summary_strip(logs)
        self._update_user_list(logs)
        if self.selected_user:
            self._show_user_detail(
                self.selected_user)
        if self._current_tab == "summary":
            self._refresh_summary()
        now = datetime.datetime.now()\
            .strftime("%H:%M:%S")
        self.refresh_lbl.configure(
            text=f"↻  {now}",
            text_color=C_DIM)
 
    def _start_polling(self):
        def _poll():
            if not self.winfo_exists():
                return
            self._refresh()
            self._poll_id = self.after(
                POLL_INTERVAL, _poll)
        self._poll_id = self.after(
            POLL_INTERVAL, _poll)
 
    # ─────────────────────────────────────────────────
    # SUMMARY STRIP — accurate calculation
    # ─────────────────────────────────────────────────
    def _update_summary_strip(self, logs: dict):
        today   = datetime.date.today().strftime(
            "%Y-%m-%d")
        total   = len(logs)
        active  = 0
        locked  = 0
        intrus  = 0
        t_events= 0
 
        for uname, udata in logs.items():
            events = udata.get("events", [])
            t_events += len(events)
 
            # Count intrusions today
            intrus += sum(
                1 for e in events
                if e.get("risk") in (
                    "MEDIUM", "HIGH")
                and e.get("timestamp", ""
                          ).startswith(today))
 
            if events:
                last = events[0]
                ts   = last.get("timestamp", "")
                risk = last.get("risk", "LOW")
                # Active = last event < 5 minutes ago
                try:
                    last_dt = datetime.datetime\
                        .strptime(ts,
                            "%Y-%m-%d %H:%M:%S")
                    diff = (
                        datetime.datetime.now()
                        - last_dt
                    ).total_seconds()
                    if diff < 300:
                        active += 1
                        if last.get("locked",
                                    False):
                            locked += 1
                except Exception:
                    pass
 
        self.stat_labels["total_users"]\
            .configure(text=str(total))
        self.stat_labels["active_users"]\
            .configure(text=str(active))
        self.stat_labels["locked_users"]\
            .configure(text=str(locked))
        self.stat_labels["intrusions_today"]\
            .configure(text=str(intrus))
        self.stat_labels["total_events"]\
            .configure(text=str(t_events))
 
    # ─────────────────────────────────────────────────
    # USER LIST
    # ─────────────────────────────────────────────────
    def _update_user_list(self, logs: dict):
        for w in self.user_list_frame\
                .winfo_children():
            w.destroy()
 
        if not logs:
            ctk.CTkLabel(
                self.user_list_frame,
                text="No users enrolled yet",
                font=("JetBrains Mono", 11),
                text_color=C_DIM
            ).pack(pady=20)
            return
 
        for uname, udata in logs.items():
            events = udata.get("events", [])
            status_color, status_dot, status_txt =\
                self._get_status(events)
            is_selected = (
                uname == self.selected_user)
 
            btn_frame = ctk.CTkFrame(
                self.user_list_frame,
                fg_color=(
                    "#1e3a5f" if is_selected
                    else C_PANEL),
                corner_radius=8)
            btn_frame.pack(fill="x", pady=3)
 
            # Status dot
            ctk.CTkLabel(btn_frame,
                text=status_dot,
                font=("JetBrains Mono", 18),
                text_color=status_color
            ).pack(side="left",
                   padx=(12, 6), pady=10)
 
            # Info
            info_f = ctk.CTkFrame(btn_frame,
                fg_color="transparent")
            info_f.pack(side="left",
                        fill="x", expand=True,
                        pady=8)
 
            ctk.CTkLabel(info_f,
                text=uname,
                font=("Syne", 13, "bold"),
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
 
            risk_color = {
                "HIGH"  : C_RED,
                "MEDIUM": C_AMBER,
                "LOW"   : C_GREEN,
            }.get(last_risk, C_DIM)
 
            ctk.CTkLabel(info_f,
                text=f"score={last_score}  "
                     f"[{last_risk}]  "
                     f"{status_txt}",
                font=("JetBrains Mono", 9),
                text_color=risk_color,
                anchor="w"
            ).pack(anchor="w")
 
            # Click to select
            for widget in [btn_frame] + \
                    list(btn_frame.winfo_children()) + \
                    list(info_f.winfo_children()):
                widget.bind(
                    "<Button-1>",
                    lambda e, u=uname:
                        self._select_user(u))
 
    def _get_status(self, events):
        if not events:
            return C_GREY, "○", "offline"
        last = events[0]
        ts   = last.get("timestamp", "")
        risk = last.get("risk", "LOW")
        locked = last.get("locked", False)
        try:
            last_dt = datetime.datetime.strptime(
                ts, "%Y-%m-%d %H:%M:%S")
            diff = (datetime.datetime.now()
                    - last_dt).total_seconds()
            if diff > 300:
                return C_GREY, "○", "offline"
        except Exception:
            return C_GREY, "○", "offline"
 
        if locked:
            return C_RED,   "●", "LOCKED"
        elif risk == "HIGH":
            return C_RED,   "●", "HIGH RISK"
        elif risk == "MEDIUM":
            return C_AMBER, "●", "warning"
        else:
            return C_GREEN, "●", "active"
 
    # ─────────────────────────────────────────────────
    # USER DETAIL
    # ─────────────────────────────────────────────────
    def _select_user(self, username: str):
        self.selected_user = username
        logs = get_all_logs()
        self._update_user_list(logs)
        self._show_user_detail(username)
 
    def _show_user_detail(self, username: str):
        logs    = get_all_logs()
        summary = get_user_summary(username)
        udata   = logs.get(username, {})
        events  = udata.get("events", [])
 
        status_color, status_dot, status_txt =\
            self._get_status(events)
 
        self.selected_lbl.configure(
            text=f"  {status_dot}  {username}  "
                 f"—  {status_txt}",
            text_color=status_color)
 
        self.user_status_lbl.configure(
            text=f"Last active: "
                 f"{summary.get('last_seen','—')}")
 
        # Stats cards
        self.user_stat_labels["enrolled_on"]\
            .configure(text=str(
                summary.get("enrolled_on","—")
            )[-16:])
        self.user_stat_labels["last_seen"]\
            .configure(text=str(
                summary.get("last_seen","—")
            )[-8:])
        self.user_stat_labels["total_events"]\
            .configure(text=str(
                summary.get("total_events", 0)))
        self.user_stat_labels["total_locks"]\
            .configure(text=str(
                summary.get("total_locks", 0)))
        self.user_stat_labels["intrusions_today"]\
            .configure(text=str(
                summary.get(
                    "intrusions_today", 0)))
 
        last_score = summary.get("last_score","—")
        last_risk  = summary.get("last_risk", "—")
        sc = {"LOW":C_GREEN,
              "MEDIUM":C_AMBER,
              "HIGH":C_RED
              }.get(last_risk, C_DIM)
        self.user_stat_labels["last_score"]\
            .configure(
                text=str(last_score),
                text_color=sc)
 
        # Populate intrusion log
        self._populate_intrusion_log(events)
 
    def _populate_intrusion_log(self,
                                 events: list):
        for w in self.intrusion_scroll\
                .winfo_children():
            w.destroy()
 
        if not events:
            ctk.CTkLabel(
                self.intrusion_scroll,
                text="No events recorded yet",
                font=("JetBrains Mono", 12),
                text_color=C_DIM
            ).pack(pady=30)
            return
 
        for evt in events[:200]:
            risk   = evt.get("risk", "LOW")
            locked = evt.get("locked", False)
 
            row_bg = (
                "#150808" if risk == "HIGH"
                else "#151000"
                    if risk == "MEDIUM"
                else "transparent")
 
            risk_color = {
                "HIGH"  : C_RED,
                "MEDIUM": C_AMBER,
                "LOW"   : C_GREEN,
            }.get(risk, C_DIM)
 
            row = ctk.CTkFrame(
                self.intrusion_scroll,
                fg_color=row_bg,
                corner_radius=4)
            row.pack(fill="x", pady=1)
 
            values = [
                (evt.get("timestamp","—"),     170),
                (str(evt.get("score","—")),     70),
                (risk,                          80),
                (f"{evt.get('dwell_ms',0):.0f}",80),
                (f"{evt.get('flight_ms',0):.0f}",80),
                (f"{evt.get('mouse_vel',0):.0f}",90),
                ("🔒 YES"
                    if locked else "no",        70),
                (str(evt.get(
                    "session_id","—")),         130),
            ]
            colors_map = [
                C_BRIGHT, C_BRIGHT,
                risk_color, C_DIM,
                C_DIM, C_DIM,
                C_RED if locked else C_GREY,
                C_DIM,
            ]
            for (val, w), col in zip(
                    values, colors_map):
                ctk.CTkLabel(row,
                    text=val,
                    width=w,
                    font=("JetBrains Mono", 10),
                    text_color=col,
                    anchor="w"
                ).pack(side="left",
                       padx=(10, 0), pady=6)
 
    # ─────────────────────────────────────────────────
    # BLOCKCHAIN PANEL
    # ─────────────────────────────────────────────────
    def _refresh_blockchain(self):
        for w in self.bc_scroll.winfo_children():
            w.destroy()
 
        bc_logs = _read_blockchain_logs()
        self.bc_count_lbl.configure(
            text=f"{len(bc_logs)} transactions")
 
        if not bc_logs:
            ctk.CTkLabel(self.bc_scroll,
                text="No blockchain transactions "
                     "found.\n\n"
                     "Make sure Ganache is running "
                     "and users are active.",
                font=("JetBrains Mono", 12),
                text_color=C_DIM,
                justify="center"
            ).pack(pady=40)
            return
 
        for evt in bc_logs:
            risk   = evt.get("risk", "LOW")
            locked = evt.get("locked", False)
            tx     = evt.get("tx_hash", "—")
 
            risk_color = {
                "HIGH"  : C_RED,
                "MEDIUM": C_AMBER,
                "LOW"   : C_GREEN,
            }.get(risk, C_DIM)
 
            row_bg = (
                "#150808" if risk == "HIGH"
                else "#151000"
                    if risk == "MEDIUM"
                else "transparent")
 
            row = ctk.CTkFrame(self.bc_scroll,
                fg_color=row_bg,
                corner_radius=4)
            row.pack(fill="x", pady=1)
 
            bc_values = [
                (evt.get("timestamp","—"),      170),
                (str(evt.get("username","—")),  100),
                (str(evt.get("score","—")),      70),
                (risk,                           80),
                ("YES" if locked else "no",      70),
                (str(evt.get(
                    "session_id","—")),          130),
                (f"⛓ {tx}",                     200),
            ]
            colors_bc = [
                C_BRIGHT,
                C_PURPLE,
                C_BRIGHT,
                risk_color,
                C_RED if locked else C_GREY,
                C_DIM,
                C_BLUE,
            ]
            for (val, w), col in zip(
                    bc_values, colors_bc):
                ctk.CTkLabel(row,
                    text=val,
                    width=w,
                    font=("JetBrains Mono", 10),
                    text_color=col,
                    anchor="w"
                ).pack(side="left",
                       padx=(10, 0), pady=6)
 
    # ─────────────────────────────────────────────────
    # SUMMARY PANEL
    # ─────────────────────────────────────────────────
    def _refresh_summary(self):
        for w in self.summary_scroll\
                .winfo_children():
            w.destroy()
 
        logs = get_all_logs()
        if not logs:
            ctk.CTkLabel(self.summary_scroll,
                text="No users enrolled yet",
                font=("JetBrains Mono", 12),
                text_color=C_DIM
            ).pack(pady=30)
            return
 
        for uname in logs:
            summary = get_user_summary(uname)
            events  = logs[uname].get(
                "events", [])
            _, _, status_txt = \
                self._get_status(events)
 
            last_risk = summary.get(
                "last_risk", "—")
            risk_color = {
                "HIGH"  : C_RED,
                "MEDIUM": C_AMBER,
                "LOW"   : C_GREEN,
            }.get(last_risk, C_DIM)
 
            row = ctk.CTkFrame(
                self.summary_scroll,
                fg_color=C_PANEL,
                corner_radius=4)
            row.pack(fill="x", pady=2)
 
            sum_values = [
                (uname,                         130),
                (str(summary.get(
                    "enrolled_on","—"))[-16:],  160),
                (str(summary.get(
                    "last_seen","—"))[-16:],    160),
                (str(summary.get(
                    "total_events", 0)),         110),
                (str(summary.get(
                    "total_locks", 0)),          100),
                (str(summary.get(
                    "intrusions_today", 0)),     140),
                (str(summary.get(
                    "last_score","—")),          100),
                (last_risk,                      100),
            ]
            sum_colors = [
                C_PURPLE, C_DIM, C_DIM,
                C_BRIGHT, C_RED, C_AMBER,
                C_BRIGHT, risk_color,
            ]
            for (val, w), col in zip(
                    sum_values, sum_colors):
                ctk.CTkLabel(row,
                    text=val,
                    width=w,
                    font=("JetBrains Mono", 10),
                    text_color=col,
                    anchor="w"
                ).pack(side="left",
                       padx=(10, 0), pady=8)
 
    # ─────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────
    def _export_user(self):
        if not self.selected_user:
            self._show_toast(
                "⚠ Select a user first",
                C_AMBER)
            return
        fname = (f"biosync_"
                 f"{self.selected_user}_"
                 f"{datetime.date.today()}.csv")
        path = os.path.join(
            os.path.expanduser("~"),
            "Desktop", fname)
        ok = export_user_csv(
            self.selected_user, path)
        if ok:
            self._show_toast(
                f"✓ Saved → Desktop/{fname}",
                C_GREEN)
        else:
            self._show_toast(
                "⚠ No data to export",
                C_AMBER)
 
    def _export_all(self):
        fname = (f"biosync_all_"
                 f"{datetime.date.today()}.csv")
        path = os.path.join(
            os.path.expanduser("~"),
            "Desktop", fname)
        ok = export_summary_csv(path)
        if ok:
            self._show_toast(
                f"✓ Saved → Desktop/{fname}",
                C_GREEN)
        else:
            self._show_toast(
                "⚠ No data to export",
                C_AMBER)
 
    def _show_toast(self, msg: str,
                    color=None):
        self.refresh_lbl.configure(
            text=msg,
            text_color=color or C_GREEN)
        self.after(3000, lambda:
            self.refresh_lbl.configure(
                text_color=C_DIM))
 
    # ─────────────────────────────────────────────────
    def _logout(self):
        self.on_hide()
        self.state['is_admin'] = False
        self.app.show_screen("login")
 