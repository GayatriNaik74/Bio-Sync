"""BioSync — Login / Signup Screen"""
import customtkinter as ctk
import json, os, hashlib, datetime

USERS_FILE = "data/users.json"

def _load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f: return json.load(f)
    return {}

def _save_users(users):
    os.makedirs("data", exist_ok=True)
    with open(USERS_FILE, 'w') as f: json.dump(users, f, indent=2)

def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()


class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color="#07070b")
        self.app   = app
        self.state = state
        self.mode  = "login"
        self._build()

    def _build(self):
        # ── Left accent bar ──────────────────────────
        bar = ctk.CTkFrame(self, width=3, fg_color="#a78bfa")
        bar.place(x=0, rely=0.2, relheight=0.6)

        # ── Center card ──────────────────────────────
        self.card = ctk.CTkFrame(
            self, width=380, height=520,
            fg_color="#0d0d14",
            corner_radius=16,
            border_width=1, border_color="#1e1e2a"
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        # ── Logo ─────────────────────────────────────
        logo_f = ctk.CTkFrame(self.card, fg_color="transparent")
        logo_f.pack(pady=(28, 0))
        ctk.CTkLabel(logo_f,
            text="⬡  BIOSYNC",
            font=("JetBrains Mono", 18, "bold"),
            text_color="#a78bfa"
        ).pack()
        ctk.CTkLabel(logo_f,
            text="behavioral authentication",
            font=("JetBrains Mono", 9),
            text_color="#3a3a55"
        ).pack(pady=(2, 0))

        # ── Mode toggle ──────────────────────────────
        tog_f = ctk.CTkFrame(self.card,
            fg_color="#111118", corner_radius=8)
        tog_f.pack(padx=30, pady=20, fill="x")
        self.login_btn = ctk.CTkButton(tog_f,
            text="Login", width=140, height=30,
            fg_color="#a78bfa", text_color="#07070b",
            font=("Syne", 12, "bold"), corner_radius=6,
            command=lambda: self._set_mode("login")
        )
        self.login_btn.pack(side="left", padx=4, pady=4)
        self.signup_btn = ctk.CTkButton(tog_f,
            text="Sign Up", width=140, height=30,
            fg_color="transparent", text_color="#3a3a55",
            font=("Syne", 12, "bold"), corner_radius=6,
            hover_color="#1a1a25",
            command=lambda: self._set_mode("signup")
        )
        self.signup_btn.pack(side="left", padx=4, pady=4)

        # ── Username ──────────────────────────────────
        ctk.CTkLabel(self.card,
            text="USERNAME",
            font=("JetBrains Mono", 9),
            text_color="#3a3a55", anchor="w"
        ).pack(padx=30, anchor="w")
        self.user_entry = ctk.CTkEntry(self.card,
            placeholder_text="enter username",
            height=40, corner_radius=8,
            fg_color="#111118", border_color="#1e1e2a",
            text_color="#d4d4f0",
            placeholder_text_color="#2e2e40",
            font=("JetBrains Mono", 12)
        )
        self.user_entry.pack(padx=30, pady=(4, 14), fill="x")

        # ── Password ──────────────────────────────────
        ctk.CTkLabel(self.card,
            text="PASSWORD",
            font=("JetBrains Mono", 9),
            text_color="#3a3a55", anchor="w"
        ).pack(padx=30, anchor="w")
        self.pass_entry = ctk.CTkEntry(self.card,
            placeholder_text="enter password",
            show="●", height=40, corner_radius=8,
            fg_color="#111118", border_color="#1e1e2a",
            text_color="#d4d4f0",
            placeholder_text_color="#2e2e40",
            font=("JetBrains Mono", 12)
        )
        self.pass_entry.pack(padx=30, pady=(4, 14), fill="x")
        self.pass_entry.bind("<Return>", lambda e: self._submit())

        # ── Status label ──────────────────────────────
        self.status = ctk.CTkLabel(self.card,
            text="", font=("JetBrains Mono", 10),
            text_color="#f87171")
        self.status.pack()

        # ── Submit button ─────────────────────────────
        self.submit_btn = ctk.CTkButton(self.card,
            text="LOGIN  →", height=42,
            fg_color="#a78bfa", hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 13, "bold"), corner_radius=8,
            command=self._submit
        )
        self.submit_btn.pack(padx=30, pady=(6, 0), fill="x")

        # ── Divider ───────────────────────────────────
        ctk.CTkFrame(self.card, height=1,
            fg_color="#1e1e2a"
        ).pack(padx=30, pady=(18, 6), fill="x")
        ctk.CTkLabel(self.card,
            text="ADMIN ACCESS",
            font=("JetBrains Mono", 8),
            text_color="#2e2e40"
        ).pack()

        # ── Admin Login button ────────────────────────
        ctk.CTkButton(self.card,
            text="🛡  Admin Login",
            height=36,
            fg_color="transparent",
            hover_color="#111118",
            text_color="#3a3a55",
            font=("Syne", 11),
            corner_radius=8,
            border_width=1,
            border_color="#1e1e2a",
            command=self._admin_login
        ).pack(padx=30, pady=(6, 18), fill="x")

    # ─────────────────────────────────────────────────
    def _set_mode(self, mode):
        self.mode = mode
        if mode == "login":
            self.login_btn.configure(
                fg_color="#a78bfa", text_color="#07070b")
            self.signup_btn.configure(
                fg_color="transparent", text_color="#3a3a55")
            self.submit_btn.configure(text="LOGIN  →")
        else:
            self.signup_btn.configure(
                fg_color="#a78bfa", text_color="#07070b")
            self.login_btn.configure(
                fg_color="transparent", text_color="#3a3a55")
            self.submit_btn.configure(text="CREATE ACCOUNT  →")
        self.status.configure(text="")

    # ─────────────────────────────────────────────────
    def _submit(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self.status.configure(text="⚠ fill all fields")
            return

        users = _load_users()

        if self.mode == "signup":
            if username in users:
                self.status.configure(text="⚠ username taken")
                return
            users[username] = {
                'password' : _hash(password),
                'enrolled' : False,
                'created'  : datetime.datetime.now().isoformat()
            }
            _save_users(users)
            self.status.configure(
                text="✓ account created!",
                text_color="#4ade80")
            self._set_mode("login")
        else:
            if (username not in users or
                    users[username]['password'] != _hash(password)):
                self.status.configure(
                    text="⚠ invalid credentials",
                    text_color="#f87171")
                return
            self.state['username']   = username
            self.state['enrolled']   = users[username].get('enrolled', False)
            self.state['is_admin']   = False
            self.state['session_id'] = (
                f"sess_{username}_"
                f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
            if self.state['enrolled']:
                self.app.show_screen("dashboard")
            else:
                self.app.show_screen("enrollment")

    # ─────────────────────────────────────────────────
    def _admin_login(self):
        """Open admin credentials popup."""
        popup = ctk.CTkToplevel(self)
        popup.title("Admin Login")
        popup.geometry("340x300")
        popup.resizable(False, False)
        popup.configure(fg_color="#0d0d14")
        popup.grab_set()
        popup.focus()

        ctk.CTkLabel(popup,
            text="🛡  ADMIN LOGIN",
            font=("JetBrains Mono", 13, "bold"),
            text_color="#a78bfa"
        ).pack(pady=(24, 4))
        ctk.CTkLabel(popup,
            text="separate admin credentials required",
            font=("JetBrains Mono", 8),
            text_color="#2e2e40"
        ).pack(pady=(0, 16))

        ctk.CTkLabel(popup, text="USERNAME",
            font=("JetBrains Mono", 8),
            text_color="#3a3a55", anchor="w"
        ).pack(padx=28, anchor="w")
        adm_user = ctk.CTkEntry(popup,
            placeholder_text="admin username",
            height=36, corner_radius=8,
            fg_color="#111118", border_color="#1e1e2a",
            text_color="#d4d4f0",
            placeholder_text_color="#2e2e40",
            font=("JetBrains Mono", 11)
        )
        adm_user.pack(padx=28, pady=(3, 10), fill="x")
        adm_user.focus()

        ctk.CTkLabel(popup, text="PASSWORD",
            font=("JetBrains Mono", 8),
            text_color="#3a3a55", anchor="w"
        ).pack(padx=28, anchor="w")
        adm_pass = ctk.CTkEntry(popup,
            placeholder_text="admin password",
            show="●", height=36, corner_radius=8,
            fg_color="#111118", border_color="#1e1e2a",
            text_color="#d4d4f0",
            placeholder_text_color="#2e2e40",
            font=("JetBrains Mono", 11)
        )
        adm_pass.pack(padx=28, pady=(3, 6), fill="x")

        err_lbl = ctk.CTkLabel(popup, text="",
            font=("JetBrains Mono", 9),
            text_color="#f87171")
        err_lbl.pack()

        def _do_login():
            import sys, os
            sys.path.insert(0, os.path.join(
                os.path.dirname(__file__), '..', 'src'))
            from admin_logger import verify_admin

            u = adm_user.get().strip()
            p = adm_pass.get()
            if not u or not p:
                err_lbl.configure(text="⚠ fill all fields")
                return
            if verify_admin(u, p):
                self.state['username'] = u
                self.state['is_admin'] = True
                popup.destroy()
                self.app.show_screen("admin_dashboard")
            else:
                err_lbl.configure(text="⚠ invalid admin credentials")

        adm_pass.bind("<Return>", lambda e: _do_login())
        ctk.CTkButton(popup,
            text="ACCESS ADMIN  →", height=38,
            fg_color="#a78bfa", hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 12, "bold"), corner_radius=8,
            command=_do_login
        ).pack(padx=28, pady=(4, 0), fill="x")


