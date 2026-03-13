"""
BioSync — Floating Desktop Meter Widget
A small always-on-top window showing live trust score.
Launch separately: python ui/meter_widget.py
Or call MeterWidget(state) from main.py after login.
"""
import customtkinter as ctk
import tkinter as tk
from ui.gauge import TrustGauge

class MeterWidget:
    def __init__(self, state: dict):
        self.state = state
        self.win   = ctk.CTkToplevel()
        self.win.title("")
        self.win.geometry("210x260+20+20")
        self.win.overrideredirect(True)   # no title bar
        self.win.wm_attributes("-topmost", True)
        self.win.wm_attributes("-alpha", 0.92)
        self.win.configure(fg_color="#0a0a12")
        self._build()
        self._enable_drag()
        self._update_loop()

    def _build(self):
        # Outer border frame
        border = ctk.CTkFrame(self.win,
            fg_color="#0a0a12", corner_radius=12,
            border_width=1, border_color="#1e1e2a")
        border.pack(fill="both", expand=True, padx=1, pady=1)

        ctk.CTkLabel(border, text="BIOSYNC",
            font=("JetBrains Mono", 8),
            text_color="#2e2e40").pack(pady=(8,0))

        row = ctk.CTkFrame(border, fg_color="transparent")
        row.pack(expand=True)

        self.dot = ctk.CTkLabel(row, text="●",
            font=("Segoe UI", 10), text_color="#4ade80")
        self.dot.pack(side="left", padx=(10,4))

        self.gauge = TrustGauge(border, size=180, bg="#0a0a12")
        self.gauge.pack()

        self.score_lbl = ctk.CTkLabel(border,
            text="—",
            font=("Syne", 13, "bold"),
            text_color="#a78bfa")
        self.score_lbl.pack(pady=(0, 8))

        self.score_lbl = ctk.CTkLabel(row,
            text="—",
            font=("Syne", 26, "bold"),
            text_color="#a78bfa")
        self.score_lbl.pack(side="left")

        self.bar = ctk.CTkProgressBar(border,
            height=3, fg_color="#1a1a25",
            progress_color="#a78bfa")
        self.bar.pack(fill="x", padx=10, pady=(4,8))
        self.bar.set(1.0)

        # Close button
        ctk.CTkButton(border, text="×", width=18, height=18,
            fg_color="transparent", text_color="#2e2e40",
            hover_color="#1a1a25", font=("Syne",12),
            command=self.win.destroy
        ).place(relx=1.0, x=-4, y=4, anchor="ne")

    def _enable_drag(self):
        def start(e): self._x=e.x; self._y=e.y
        def drag(e):
            dx=e.x-self._x; dy=e.y-self._y
            x=self.win.winfo_x()+dx
            y=self.win.winfo_y()+dy
            self.win.geometry(f"+{x}+{y}")
        self.win.bind("<ButtonPress-1>", start)
        self.win.bind("<B1-Motion>", drag)

    def _update_loop(self):
        score = self.state.get('trust_score', 100)
        risk  = self.state.get('risk_level', 'LOW')
        color = {'LOW':"#4ade80",
                 'MEDIUM':"#fbbf24",
                 'HIGH':"#f87171"}[risk]
        self.gauge.set_score(score) 
        self.score_lbl.configure(
            text=f"{score:.0f}", text_color=color)
        self.dot.configure(text_color=color)
        self.bar.configure(progress_color=color)
        self.bar.set(score / 100)
        self.win.after(2000, self._update_loop)

# ── Standalone launch ─────────────────────────────
if __name__ == "__main__":
    # Demo with fake state that changes every 3 seconds
    import random
    demo_state = {'trust_score': 85.0, 'risk_level': 'LOW'}
    root = ctk.CTk()
    root.withdraw()  # hide root window
    m = MeterWidget(demo_state)
    def fake_update():
        demo_state['trust_score'] = random.uniform(30, 95)
        s = demo_state['trust_score']
        demo_state['risk_level'] = (
            'LOW' if s>=80 else 'MEDIUM' if s>=60 else 'HIGH')
        root.after(3000, fake_update)
    root.after(3000, fake_update)
    root.mainloop()