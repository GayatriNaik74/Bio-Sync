"""
BioSync — ui/gauge.py
Option C: Minimal Arc + Dot gauge
Red → Yellow → Green gradient arc, score dot tracker, large centred score number.

Usage:
    from ui.gauge import TrustGauge
    g = TrustGauge(parent, size=260)
    g.pack()
    g.set_score(85.0)   # call anytime — animates smoothly
"""

import tkinter as tk
import math


class TrustGauge(tk.Canvas):

    def __init__(self, parent, size=260, bg="#0d0d14", **kw):
        self.SIZE  = size
        self.CX    = size // 2
        self.CY    = int(size * 0.54)
        self.R     = int(size * 0.38)

        super().__init__(
            parent,
            width=size,
            height=int(size * 0.62),
            bg=bg,
            highlightthickness=0,
            **kw,
        )
        self._bg       = bg
        self._score    = 100.0
        self._cur      = 100.0
        self._anim_id  = None
        self.after(60, lambda: self._draw(self._cur))

    # ─────────────────────────────────────────────────
    # COLOUR HELPERS
    # ─────────────────────────────────────────────────
    def _arc_color(self, t):
        """
        t = 0.0 → left (score 0, red)
        t = 1.0 → right (score 100, green)
        Returns '#rrggbb'.
        """
        stops = [
            (0.00, (220, 50,  50)),
            (0.30, (230, 140, 20)),
            (0.55, (220, 200, 20)),
            (0.78, (130, 200, 30)),
            (1.00, (40,  200, 70)),
        ]
        lo, hi = stops[0], stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                lo, hi = stops[i], stops[i + 1]
                break
        span = hi[0] - lo[0]
        f    = 0.0 if span == 0 else (t - lo[0]) / span
        r = int(lo[1][0] + (hi[1][0] - lo[1][0]) * f)
        g = int(lo[1][1] + (hi[1][1] - lo[1][1]) * f)
        b = int(lo[1][2] + (hi[1][2] - lo[1][2]) * f)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _score_color(self, score):
        if score < 52:
            return "#f87171"
        elif score < 68:
            return "#fbbf24"
        else:
            return "#4ade80"

    def _blend(self, hex_col, alpha):
        """Blend a hex colour with the canvas background for fake transparency."""
        bg_hex = self._bg.lstrip("#")
        if len(bg_hex) == 3:
            bg_hex = "".join(c*2 for c in bg_hex)
        br = int(bg_hex[0:2], 16)
        bg = int(bg_hex[2:4], 16)
        bb = int(bg_hex[4:6], 16)
        col = hex_col.lstrip("#")
        cr  = int(col[0:2], 16)
        cg  = int(col[2:4], 16)
        cb  = int(col[4:6], 16)
        r = int(br + (cr - br) * alpha)
        g = int(bg + (cg - bg) * alpha)
        b = int(bb + (cb - bb) * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ─────────────────────────────────────────────────
    # GEOMETRY
    # ─────────────────────────────────────────────────
    def _angle(self, score):
        """Score 0→100 maps to π→0 (left half-circle to right)."""
        return math.pi - (score / 100.0) * math.pi

    def _xy(self, r, angle_rad):
        return (
            self.CX + r * math.cos(angle_rad),
            self.CY + r * math.sin(angle_rad),
        )

    # ─────────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────────
    def _draw(self, score):
        self.delete("all")
        CX, CY, R = self.CX, self.CY, self.R
        STEPS     = 90
        TH_BG     = max(6, self.SIZE // 32)   # background track thickness
        TH_ARC    = max(5, TH_BG - 2)         # gradient arc thickness

        score_ang = self._angle(score)
        col       = self._score_color(score)

        # ── 1. Background track ──────────────────────
        pts_bg = []
        for i in range(STEPS + 1):
            a = math.pi - (i / STEPS) * math.pi
            pts_bg += [CX + R * math.cos(a), CY + R * math.sin(a)]
        if len(pts_bg) >= 4:
            self.create_line(
                pts_bg,
                fill="#181825",
                width=TH_BG + 4,
                smooth=False,
                capstyle="round",
            )

        # ── 2. Full gradient arc (muted) ─────────────
        for i in range(STEPS):
            t0 = i / STEPS
            t1 = (i + 1) / STEPS
            a0 = math.pi - t0 * math.pi
            a1 = math.pi - t1 * math.pi
            base_col = self._arc_color((t0 + t1) / 2)
            muted    = self._blend(base_col, 0.28)
            seg = []
            for k in range(5):
                a = a0 + (a1 - a0) * k / 4
                seg += [CX + R * math.cos(a), CY + R * math.sin(a)]
            if len(seg) >= 4:
                self.create_line(
                    seg, fill=muted,
                    width=TH_ARC, smooth=False, capstyle="butt")

        # ── 3. Bright scored arc (left → score pos) ──
        scored_steps = max(1, int(STEPS * score / 100))
        for i in range(scored_steps):
            t0 = i / STEPS
            t1 = (i + 1) / STEPS
            a0 = math.pi - t0 * math.pi
            a1 = math.pi - t1 * math.pi
            bright_col = self._arc_color((t0 + t1) / 2)
            seg = []
            for k in range(5):
                a = a0 + (a1 - a0) * k / 4
                seg += [CX + R * math.cos(a), CY + R * math.sin(a)]
            if len(seg) >= 4:
                self.create_line(
                    seg, fill=bright_col,
                    width=TH_ARC, smooth=False, capstyle="butt")

        # ── 4. Score label — large centred number ────
        font_size  = max(14, self.SIZE // 9)
        label_size = max(9,  self.SIZE // 24)

        self.create_text(
            CX, CY - int(R * 0.38),
            text=str(int(round(score))),
            fill=col,
            font=("JetBrains Mono", font_size, "bold"),
            anchor="center",
        )
        self.create_text(
            CX, CY - int(R * 0.10),
            text="TRUST SCORE",
            fill=self._blend("#ffffff", 0.22),
            font=("JetBrains Mono", label_size),
            anchor="center",
        )

        # ── 5. Dot tracker on arc ────────────────────
        dot_x, dot_y = self._xy(R, score_ang)
        dot_r_outer  = max(5, TH_ARC // 2 + 3)
        dot_r_inner  = max(3, dot_r_outer - 3)

        # Outer coloured ring
        self.create_oval(
            dot_x - dot_r_outer, dot_y - dot_r_outer,
            dot_x + dot_r_outer, dot_y + dot_r_outer,
            fill=col, outline="",
        )
        # White centre
        self.create_oval(
            dot_x - dot_r_inner, dot_y - dot_r_inner,
            dot_x + dot_r_inner, dot_y + dot_r_inner,
            fill="#ffffff", outline="",
        )

        # ── 6. End labels: 0 and 100 ─────────────────
        end_col = self._blend("#ffffff", 0.25)
        lx0, ly0 = self._xy(R + int(R * 0.18), math.pi)
        lx1, ly1 = self._xy(R + int(R * 0.18), 0)
        self.create_text(
            lx0, ly0 + 4,
            text="0",
            fill=end_col,
            font=("JetBrains Mono", label_size),
            anchor="center",
        )
        self.create_text(
            lx1, ly1 + 4,
            text="100",
            fill=end_col,
            font=("JetBrains Mono", label_size),
            anchor="center",
        )

        # ── 7. Risk label below score ─────────────────
        risk = "HIGH RISK" if score < 52 else "MEDIUM RISK" if score < 68 else "LOW RISK"
        self.create_text(
            CX, CY + int(R * 0.22),
            text=risk,
            fill=col,
            font=("JetBrains Mono", label_size, "bold"),
            anchor="center",
        )

    # ─────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────
    def set_score(self, score: float):
        """Smoothly animate needle to new score (0–100)."""
        self._score = max(0.0, min(100.0, float(score)))
        if self._anim_id:
            self.after_cancel(self._anim_id)
        self._animate()

    def _animate(self):
        diff = self._score - self._cur
        if abs(diff) < 0.3:
            self._cur = self._score
            self._draw(self._cur)
            return
        self._cur += diff * 0.14
        self._draw(self._cur)
        self._anim_id = self.after(16, self._animate)  # ~60 fps