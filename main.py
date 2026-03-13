"""
BioSync — main.py
Entry point. Launches the app and manages screen navigation.
Run: python main.py
"""
import sys, os, ctypes

# ── Windows DPI + tkinter fix for Python 3.13 ──────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import customtkinter as ctk
sys.path.insert(0, 'src')

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

APP_STATE = {
    'username'     : None,
    'enrolled'     : False,
    'session_id'   : None,
    'trust_score'  : 100.0,
    'risk_level'   : 'LOW',
    'baseline_path': 'models/user_baseline.pkl',
}

class BioSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BioSync")
        self.geometry("900x600")
        self.minsize(800, 520)
        self.configure(fg_color="#07070b")
        self.resizable(True, True)

        self.container = ctk.CTkFrame(self, fg_color="#07070b")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self._build_frames()
        self.show_screen("login")

    def _build_frames(self):
        from ui.login       import LoginScreen
        from ui.enrollment  import EnrollmentScreen
        from ui.dashboard   import DashboardScreen
        from ui.lock_screen import LockScreen
        from ui.profile     import ProfileScreen

        for name, ScreenClass in [
            ("login",      LoginScreen),
            ("enrollment", EnrollmentScreen),
            ("dashboard",  DashboardScreen),
            ("lock",       LockScreen),
            ("profile",    ProfileScreen),
        ]:
            frame = ScreenClass(
                parent=self.container,
                app=self,
                state=APP_STATE
            )
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[name] = frame

    def show_screen(self, name: str):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()

if __name__ == "__main__":
    app = BioSyncApp()
    app.mainloop()