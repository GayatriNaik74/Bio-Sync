"""BioSync — User Profile Screen"""
import customtkinter as ctk
import joblib, os, json, glob

class ProfileScreen(ctk.CTkFrame):
    def __init__(self, parent, app, state):
        super().__init__(parent, fg_color="#07070b")
        self.app   = app
        self.state = state
        self._build()

    def on_show(self): self._refresh()

    def _build(self):
        # ── Header ──────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="#0a0a10",
                            height=64, corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⬡  BIOSYNC",
            font=("JetBrains Mono",13,"bold"),
            text_color="#a78bfa").pack(side="left",padx=24)
        ctk.CTkButton(hdr, text="← Dashboard",
            fg_color="transparent", text_color="#3a3a55",
            hover_color="#111118", font=("Syne",12), width=110,
            command=lambda: self.app.show_screen("dashboard")
        ).pack(side="right", padx=20)

        # ── Body ────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(expand=True, fill="both", padx=60, pady=40)

        ctk.CTkLabel(body, text="Profile",
            font=("Syne",28,"bold"), text_color="#d4d4f0"
        ).pack(anchor="w", pady=(0,24))

        two = ctk.CTkFrame(body, fg_color="transparent")
        two.pack(fill="x", pady=(0,20))

        # Left card — identity
        left = ctk.CTkFrame(two,
            fg_color="#0d0d14", corner_radius=12,
            border_width=1, border_color="#1e1e2a")
        left.pack(side="left", fill="both", expand=True, padx=(0,10))

        ctk.CTkLabel(left, text="IDENTITY",
            font=("JetBrains Mono",9), text_color="#3a3a55"
        ).pack(padx=20, pady=(16,12), anchor="w")
        self.identity_labels = {}
        for k in ["Username", "Enrolled", "Sessions"]:
            r = ctk.CTkFrame(left, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(r, text=k,
                font=("JetBrains Mono",10),
                text_color="#2e2e40").pack(side="left")
            lbl = ctk.CTkLabel(r, text="—",
                font=("JetBrains Mono",10),
                text_color="#d4d4f0")
            lbl.pack(side="right")
            self.identity_labels[k] = lbl
        ctk.CTkButton(left, text="Re-enroll", height=34,
            fg_color="#141420", hover_color="#1e1e2a",
            text_color="#a78bfa", font=("Syne",12),
            border_width=1, border_color="#2e2e40",
            corner_radius=6,
            command=lambda: self.app.show_screen("enrollment")
        ).pack(padx=20, pady=16, fill="x")

        # Right card — model info
        right = ctk.CTkFrame(two,
            fg_color="#0d0d14", corner_radius=12,
            border_width=1, border_color="#1e1e2a")
        right.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(right, text="MODEL INFO",
            font=("JetBrains Mono",9), text_color="#3a3a55"
        ).pack(padx=20, pady=(16,12), anchor="w")
        self.model_labels = {}
        for k in ["Threshold", "Mean Score", "Model file"]:
            r = ctk.CTkFrame(right, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(r, text=k,
                font=("JetBrains Mono",10),
                text_color="#2e2e40").pack(side="left")
            lbl = ctk.CTkLabel(r, text="—",
                font=("JetBrains Mono",10),
                text_color="#d4d4f0")
            lbl.pack(side="right")
            self.model_labels[k] = lbl

        # Logout
        ctk.CTkButton(body, text="Log Out", height=38,
            fg_color="transparent", hover_color="#1a0a0a",
            text_color="#f87171", font=("Syne",12),
            border_width=1, border_color="#2e1515",
            corner_radius=6, width=120,
            command=lambda: self.app.show_screen("login")
        ).pack(anchor="w")

    def _refresh(self):
        uname   = self.state.get('username', '—')
        n_sess  = len(glob.glob("data/raw/session_*.csv"))
        enrolled= "Yes" if self.state.get('enrolled') else "No"
        self.identity_labels["Username"].configure(text=uname)
        self.identity_labels["Enrolled"].configure(text=enrolled)
        self.identity_labels["Sessions"].configure(text=str(n_sess))
        bl_path = "models/user_baseline.pkl"
        if os.path.exists(bl_path):
            bl = joblib.load(bl_path)
            self.model_labels["Threshold"].configure(
                text=f"{bl['threshold']:.4f}")
            self.model_labels["Mean Score"].configure(
                text=f"{bl['mean_score']:.4f}")
            self.model_labels["Model file"].configure(
                text="user_baseline.pkl ✓")