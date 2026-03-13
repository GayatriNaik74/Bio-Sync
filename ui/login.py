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
        self.mode  = "login"   # or "signup"
        self._build()

    def _build(self):
        # ── Left accent bar ────────────────────────────
        bar = ctk.CTkFrame(self, width=3, fg_color="#a78bfa")
        bar.place(x=0, rely=0.2, relheight=0.6)

        # ── Center card ────────────────────────────────
        self.card = ctk.CTkFrame(
            self, width=380, height=460,
            fg_color="#0d0d14",
            corner_radius=16,
            border_width=1, border_color="#1e1e2a"
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        # ── Logo ───────────────────────────────────────
        logo_f = ctk.CTkFrame(self.card, fg_color="transparent")
        logo_f.pack(pady=(30,0))
        ctk.CTkLabel(logo_f,
            text="⬡  BIOSYNC",
            font=("JetBrains Mono", 18, "bold"),
            text_color="#a78bfa"
        ).pack()
        ctk.CTkLabel(logo_f,
            text="behavioral authentication",
            font=("JetBrains Mono", 9),
            text_color="#3a3a55"
        ).pack(pady=(2,0))

        # ── Mode toggle ────────────────────────────────
        tog_f = ctk.CTkFrame(self.card,
            fg_color="#111118", corner_radius=8)
        tog_f.pack(padx=30, pady=22, fill="x")
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

        # ── Username ───────────────────────────────────
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
        self.user_entry.pack(padx=30, pady=(4,14), fill="x")

        # ── Password ───────────────────────────────────
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
        self.pass_entry.pack(padx=30, pady=(4,20), fill="x")
        self.pass_entry.bind("<Return>", lambda e: self._submit())

        # ── Status label ───────────────────────────────
        self.status = ctk.CTkLabel(self.card,
            text="", font=("JetBrains Mono", 10),
            text_color="#f87171")
        self.status.pack()

        # ── Submit button ──────────────────────────────
        self.submit_btn = ctk.CTkButton(self.card,
            text="LOGIN  →", height=42,
            fg_color="#a78bfa", hover_color="#7c3aed",
            text_color="#07070b",
            font=("Syne", 13, "bold"), corner_radius=8,
            command=self._submit
        )
        self.submit_btn.pack(padx=30, pady=(8,0), fill="x")

    def _set_mode(self, mode):
        self.mode = mode
        if mode == "login":
            self.login_btn.configure(fg_color="#a78bfa", text_color="#07070b")
            self.signup_btn.configure(fg_color="transparent", text_color="#3a3a55")
            self.submit_btn.configure(text="LOGIN  →")
        else:
            self.signup_btn.configure(fg_color="#a78bfa", text_color="#07070b")
            self.login_btn.configure(fg_color="transparent", text_color="#3a3a55")
            self.submit_btn.configure(text="CREATE ACCOUNT  →")
        self.status.configure(text="")

    def _submit(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self.status.configure(text="⚠ fill all fields"); return

        users = _load_users()

        if self.mode == "signup":
            if username in users:
                self.status.configure(text="⚠ username taken"); return
            users[username] = {
                'password' : _hash(password),
                'enrolled' : False,
                'created'  : datetime.datetime.now().isoformat()
            }
            _save_users(users)
            self.status.configure(text="✓ account created!",
                                     text_color="#4ade80")
            self._set_mode("login")
        else:
            if username not in users or \
               users[username]['password'] != _hash(password):
                self.status.configure(
                    text="⚠ invalid credentials",
                    text_color="#f87171"); return
            # Login success
            self.state['username']  = username
            self.state['enrolled']   = users[username].get('enrolled', False)
            self.state['session_id'] = f"sess_{username}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if self.state['enrolled']:
                self.app.show_screen("dashboard")
            else:
                self.app.show_screen("enrollment")