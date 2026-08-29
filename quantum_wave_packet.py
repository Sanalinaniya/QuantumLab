"""
QUANTUM WAVE PACKET — Module 3
A localized Gaussian wave packet, free particle (V = 0), evolving in time.

Exact analytic solution used (verified numerically against direct
integration before this file was written):

    tau(t)   = hbar*t / (2*m*sigma0^2)
    xc(t)    = x0 + (hbar*k0/m)*t                    [classical trajectory]
    Psi(x,t) = (2*pi*sigma0^2)^(-1/4) / sqrt(1+i*tau)
               * exp[ i*(k0*(x-x0) - hbar*k0^2*t/(2m)) ]
               * exp[ -(x-xc)^2 / (4*sigma0^2*(1+i*tau)) ]

For a free particle, <p> and Delta_p are exactly conserved (only Delta_x
grows) — so they're computed once per parameter change, not every frame.

Run:
    pip install numpy matplotlib PyQt5
    python quantum_wave_packet.py
"""

import sys
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QSlider, QCheckBox, QPushButton, QGroupBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


# =====================================================================
# PHYSICS — Free-particle Gaussian wave packet
# Natural units: hbar = 1, m = 1.
# =====================================================================

HBAR = 1.0
MASS = 1.0


def wavepacket(x, t, x0, k0, sigma0, m=MASS, hbar=HBAR):
    tau = hbar * t / (2 * m * sigma0 ** 2)
    denom = 1 + 1j * tau
    prefactor = (2 * np.pi * sigma0 ** 2) ** (-0.25) / np.sqrt(denom)
    xc = x0 + (hbar * k0 / m) * t
    exponent = -(x - xc) ** 2 / (4 * sigma0 ** 2 * denom)
    phase = 1j * (k0 * (x - x0) - hbar * k0 ** 2 * t / (2 * m))
    return prefactor * np.exp(phase) * np.exp(exponent)


def classical_center(t, x0, k0, m=MASS, hbar=HBAR):
    return x0 + (hbar * k0 / m) * t


def delta_x(t, sigma0, m=MASS, hbar=HBAR):
    return sigma0 * np.sqrt(1 + (hbar * t / (2 * m * sigma0 ** 2)) ** 2)


def delta_p(sigma0, hbar=HBAR):
    """Constant for a free particle — only Delta_x grows with time."""
    return hbar / (2 * sigma0)


def expectation_p(k0, hbar=HBAR):
    """Constant for a free particle."""
    return hbar * k0


# =====================================================================
# Matplotlib-in-Qt canvas
# =====================================================================

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, width=8, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)


X0_MIN_TENTHS, X0_MAX_TENTHS, X0_DEFAULT_TENTHS = -50, 50, 0
K0_MIN_TENTHS, K0_MAX_TENTHS, K0_DEFAULT_TENTHS = -50, 50, 20
SIGMA_MIN_TENTHS, SIGMA_MAX_TENTHS, SIGMA_DEFAULT_TENTHS = 3, 25, 10

X_RANGE = 25          # half-width of the plotted/simulated x window
N_POINTS = 700
DT = 0.06              # simulated time advanced per animation frame
FRAME_MS = 40           # ~25 fps


class WavePacketView(QWidget):
    def __init__(self):
        super().__init__()
        self.x0 = X0_DEFAULT_TENTHS / 10
        self.k0 = K0_DEFAULT_TENTHS / 10
        self.sigma0 = SIGMA_DEFAULT_TENTHS / 10
        self.t = 0.0
        self.playing = False

        self.show_real = True
        self.show_imag = True
        self.show_prob = True

        # History of (t, Delta_x, Delta_x*Delta_p) for the trend plot —
        # makes the growth of the uncertainty product visible as a
        # curve over time, not just a single flickering number.
        self.history_t = []
        self.history_dx = []
        self.history_product = []

        self.x = None  # computed dynamically each frame — see _current_view_window

        self._build_ui()
        self._refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    # -----------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(14, 14, 14, 14)

        self.setStyleSheet(self._stylesheet())

        root.addWidget(self._build_title())
        root.addWidget(self._build_controls())
        root.addLayout(self._build_main_row())

    def _stylesheet(self):
        return """
            QWidget { font-size: 13px; }
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                margin-top: 14px;
                padding: 12px 10px 10px 10px;
                background-color: #fefefe;
                font-weight: 700;
                font-size: 13px;
                color: #334155;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #7c3aed;
                font-size: 14px;
            }
            QLabel { color: #334155; font-weight: 600; }
            QSlider::groove:horizontal {
                height: 7px; background: #e2e8f0; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qradialgradient(cx:0.4, cy:0.4, radius:0.8,
                            fx:0.4, fy:0.4, stop:0 #a78bfa, stop:1 #7c3aed);
                width: 18px; height: 18px; margin: -6px 0;
                border-radius: 9px; border: 1px solid #6d28d9;
            }
            QSlider::sub-page:horizontal { background: #c4b5fd; border-radius: 3px; }
            QCheckBox { font-weight: 600; }
            QCheckBox::indicator { width: 15px; height: 15px; }
            QCheckBox::indicator:checked {
                background-color: #10b981; border: 1px solid #059669; border-radius: 3px;
            }
            QPushButton {
                font-weight: 700; font-size: 14px;
                padding: 6px 18px; border-radius: 8px;
                border: 1px solid #7c3aed; color: #7c3aed; background: #f5f3ff;
            }
            QPushButton:hover { background: #ede9fe; }
            QPushButton:pressed { background: #ddd6fe; }
        """

    def _build_title(self):
        label = QLabel("⚛️  QUANTUM WAVE PACKET")
        font = QFont()
        font.setPointSize(17)
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("color: #6d28d9;")
        return label

    def _build_controls(self):
        box = QGroupBox("Controls")
        outer = QVBoxLayout(box)

        # --- sliders ---
        self.x0_label, x0_row = self._make_slider_row(
            "Initial position  x₀", X0_MIN_TENTHS, X0_MAX_TENTHS,
            X0_DEFAULT_TENTHS, self._on_x0_changed)
        self.k0_label, k0_row = self._make_slider_row(
            "Momentum  k₀", K0_MIN_TENTHS, K0_MAX_TENTHS,
            K0_DEFAULT_TENTHS, self._on_k0_changed)
        self.sigma_label, sigma_row = self._make_slider_row(
            "Width  σ", SIGMA_MIN_TENTHS, SIGMA_MAX_TENTHS,
            SIGMA_DEFAULT_TENTHS, self._on_sigma_changed)
        outer.addLayout(x0_row)
        outer.addLayout(k0_row)
        outer.addLayout(sigma_row)

        # --- playback + time ---
        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶  Play")
        self.pause_btn = QPushButton("⏸  Pause")
        self.reset_btn = QPushButton("↻  Reset")
        self.play_btn.clicked.connect(self._on_play)
        self.pause_btn.clicked.connect(self._on_pause)
        self.reset_btn.clicked.connect(self._on_reset)

        self.time_label = QLabel(f"Time  t = {self.t:.2f}")
        self.time_label.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")

        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.pause_btn)
        play_row.addWidget(self.reset_btn)
        play_row.addStretch()
        play_row.addWidget(self.time_label)
        outer.addLayout(play_row)

        # --- display toggles ---
        toggle_row = QHBoxLayout()
        self.real_checkbox = QCheckBox("Show real part  Re(Ψ)")
        self.imag_checkbox = QCheckBox("Show imaginary part  Im(Ψ)")
        self.prob_checkbox = QCheckBox("Show probability density  |Ψ|²")
        self.real_checkbox.setChecked(True)
        self.imag_checkbox.setChecked(True)
        self.prob_checkbox.setChecked(True)
        self.real_checkbox.stateChanged.connect(self._on_toggle_real)
        self.imag_checkbox.stateChanged.connect(self._on_toggle_imag)
        self.prob_checkbox.stateChanged.connect(self._on_toggle_prob)
        toggle_row.addWidget(self.real_checkbox)
        toggle_row.addWidget(self.imag_checkbox)
        toggle_row.addWidget(self.prob_checkbox)
        toggle_row.addStretch()
        outer.addLayout(toggle_row)

        return box

    def _make_slider_row(self, name, lo, hi, default, handler):
        row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setMinimumWidth(160)
        value_label = QLabel(f"{default / 10:.1f}")
        value_label.setMinimumWidth(45)
        value_label.setStyleSheet("font-weight: 800; color: #7c3aed;")
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(lo)
        slider.setMaximum(hi)
        slider.setValue(default)
        slider.valueChanged.connect(handler)
        row.addWidget(name_label)
        row.addWidget(value_label)
        row.addWidget(slider)
        return value_label, row

    def _build_main_row(self):
        row = QHBoxLayout()

        self.canvas = MplCanvas(width=8, height=5)
        row.addWidget(self.canvas, stretch=3)

        side_col = QVBoxLayout()
        info_panel = self._build_info_panel()
        info_panel.setMinimumWidth(230)
        side_col.addWidget(info_panel, stretch=0)

        trend_box = QGroupBox("Uncertainty over time")
        trend_layout = QVBoxLayout(trend_box)
        self.trend_canvas = MplCanvas(width=3, height=2.4)
        self.trend_canvas.setMinimumHeight(240)
        trend_layout.addWidget(self.trend_canvas)
        side_col.addWidget(trend_box, stretch=1)

        row.addLayout(side_col, stretch=1)

        return row

    def _build_info_panel(self):
        box = QGroupBox("Quantum State")
        layout = QGridLayout(box)
        layout.setVerticalSpacing(10)

        def value_label():
            lbl = QLabel("—")
            lbl.setStyleSheet("font-weight: 800; font-size: 14px; color: #0f172a;")
            return lbl

        rows = ["⟨x⟩", "⟨p⟩", "Δx", "Δp", "Δx · Δp", "ħ/2"]
        self.info_values = {}
        for i, name in enumerate(rows):
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("font-size: 13px;")
            layout.addWidget(name_lbl, i, 0)
            val = value_label()
            self.info_values[name] = val
            layout.addWidget(val, i, 1)

        self.uncertainty_verdict = QLabel("")
        self.uncertainty_verdict.setWordWrap(True)
        self.uncertainty_verdict.setStyleSheet(
            "font-weight: 800; font-size: 13px; margin-top: 8px;"
        )
        layout.addWidget(self.uncertainty_verdict, len(rows), 0, 1, 2)

        layout.setRowStretch(len(rows) + 1, 1)
        return box

    # -----------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------
    def _on_x0_changed(self, v):
        self.x0 = v / 10
        self.x0_label.setText(f"{self.x0:.1f}")
        self._reset_time()

    def _on_k0_changed(self, v):
        self.k0 = v / 10
        self.k0_label.setText(f"{self.k0:.1f}")
        self._reset_time()

    def _on_sigma_changed(self, v):
        self.sigma0 = v / 10
        self.sigma_label.setText(f"{self.sigma0:.1f}")
        self._reset_time()

    def _on_toggle_real(self, state):
        self.show_real = bool(state)
        self._refresh()

    def _on_toggle_imag(self, state):
        self.show_imag = bool(state)
        self._refresh()

    def _on_toggle_prob(self, state):
        self.show_prob = bool(state)
        self._refresh()

    def _on_play(self):
        self.playing = True
        self.timer.start(FRAME_MS)

    def _on_pause(self):
        self.playing = False
        self.timer.stop()

    def _on_reset(self):
        self._on_pause()
        self.t = 0.0
        self._clear_history()
        self._refresh()

    def _reset_time(self):
        # Changing a parameter mid-flight would show a discontinuous
        # jump, so playback pauses and time resets — the user re-plays
        # deliberately with the new settings.
        self._on_pause()
        self.t = 0.0
        self._clear_history()
        self._refresh()

    def _clear_history(self):
        self.history_t = []
        self.history_dx = []
        self.history_product = []

    def _on_tick(self):
        self.t += DT
        self._refresh()

    # -----------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------
    def _refresh(self):
        self.time_label.setText(f"Time  t = {self.t:.2f}")
        self._draw_plot()
        self._update_info_panel()
        self._record_history()
        self._draw_trend()
        self.canvas.draw_idle()
        self.trend_canvas.draw_idle()

    def _record_history(self):
        dx = delta_x(self.t, self.sigma0)
        dp = delta_p(self.sigma0)
        # Avoid piling up duplicate points if paused/idle at the same t.
        if not self.history_t or self.history_t[-1] != self.t:
            self.history_t.append(self.t)
            self.history_dx.append(dx)
            self.history_product.append(dx * dp)

    def _draw_trend(self):
        ax = self.trend_canvas.axes
        ax.clear()
        self.trend_canvas.fig.set_facecolor("#ffffff")
        ax.set_facecolor("#fafaf9")

        if len(self.history_t) >= 2:
            ax.grid(True, color="#e2e8f0", linewidth=0.5, alpha=0.5)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)

            ax.plot(self.history_t, self.history_dx, color="#7c3aed",
                     lw=2.2, label="Δx(t)")
            ax.plot(self.history_t, self.history_product, color="#f97316",
                     lw=2.2, label="Δx·Δp(t)")
            ax.axhline(HBAR / 2, color="#94a3b8", linestyle="--", lw=1.2,
                        label="ħ/2")
            ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
            ax.set_xlabel("t", fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=9)
        else:
            # Nothing recorded yet — show a clean blank panel with just
            # the message, rather than an empty axis with meaningless
            # default 0-to-1 ticks that have no data behind them.
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.text(0.5, 0.5, "Press Play to\nsee the trend",
                     ha="center", va="center", fontsize=10, color="#94a3b8",
                     transform=ax.transAxes)

    def _current_view_window(self):
        """
        The view auto-follows the packet: centered on its current
        classical position, with a half-width that scales with its
        current spread (Delta_x). A floor keeps narrow/early packets
        from being framed too tightly, and a little extra margin
        ensures the Gaussian tails are fully visible, not clipped.
        """
        xc = classical_center(self.t, self.x0, self.k0)
        dx = delta_x(self.t, self.sigma0)
        half_width = max(6.0, dx * 5.5)
        return xc, half_width

    def _draw_plot(self):
        ax = self.canvas.axes
        ax.clear()
        self.canvas.fig.set_facecolor("#ffffff")
        ax.set_facecolor("#fafaf9")
        ax.grid(True, color="#e2e8f0", linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        xc, half_width = self._current_view_window()
        # Simulate over a slightly wider range than the visible window
        # so curves don't look abruptly cut off right at the plot edge.
        x = np.linspace(xc - half_width * 1.15, xc + half_width * 1.15, N_POINTS)
        self.x = x
        psi = wavepacket(x, self.t, self.x0, self.k0, self.sigma0)

        if self.show_prob:
            prob = np.abs(psi) ** 2
            # Soft glow behind the peak — a couple of wide, low-alpha
            # strokes underneath the crisp line, echoing the "shine"
            # used for the selected level in Module 2. Kept subtle:
            # this is a physics plot, not a poster.
            ax.plot(x, prob, color="#fdba74", lw=7, alpha=0.25, zorder=3)
            ax.plot(x, prob, color="#f97316", lw=2.4, label="|Ψ(x,t)|²", zorder=4)
            ax.fill_between(x, 0, prob, color="#fb923c", alpha=0.22, zorder=2)

        if self.show_real:
            ax.plot(x, psi.real, color="#c4b5fd", lw=4, alpha=0.3, zorder=2)
            ax.plot(x, psi.real, color="#7c3aed", lw=1.6, label="Re(Ψ)", zorder=3)

        if self.show_imag:
            ax.plot(x, psi.imag, color="#67e8f9", lw=4, alpha=0.3, zorder=2)
            ax.plot(x, psi.imag, color="#06b6d4", lw=1.6, label="Im(Ψ)", zorder=3)

        # Marker for the classical center <x>(t) — a light visual anchor.
        ax.axvline(xc, color="#94a3b8", linestyle=":", lw=1, zorder=1)

        ax.axhline(0, color="#cbd5e1", lw=0.6, zorder=1)
        ax.set_xlim(xc - half_width, xc + half_width)
        y_headroom = max(0.8, np.max(np.abs(psi)) * 1.4)
        ax.set_ylim(-y_headroom, y_headroom)
        ax.set_xlabel("x", fontweight="bold")
        ax.set_ylabel("amplitude / probability density", fontweight="bold")
        ax.set_title("Free-particle Gaussian wave packet", fontsize=13, fontweight="bold", color="#334155")
        if self.show_real or self.show_imag or self.show_prob:
            ax.legend(loc="upper right", fontsize=9, framealpha=0.92,
                       fancybox=True, edgecolor="#e2e8f0")

    def _update_info_panel(self):
        x_ev = classical_center(self.t, self.x0, self.k0)
        p_ev = expectation_p(self.k0)
        dx = delta_x(self.t, self.sigma0)
        dp = delta_p(self.sigma0)
        product = dx * dp
        bound = HBAR / 2

        self.info_values["⟨x⟩"].setText(f"{x_ev:.3f}")
        self.info_values["⟨p⟩"].setText(f"{p_ev:.3f}")
        self.info_values["Δx"].setText(f"{dx:.3f}")
        self.info_values["Δp"].setText(f"{dp:.3f}")
        self.info_values["Δx · Δp"].setText(f"{product:.4f}")
        self.info_values["ħ/2"].setText(f"{bound:.4f}")

        satisfied = product >= bound - 1e-9
        if satisfied:
            self.uncertainty_verdict.setStyleSheet(
                "font-weight: 800; font-size: 12px; margin-top: 8px; color: #059669;"
            )
            self.uncertainty_verdict.setText("✓ Δx·Δp ≥ ħ/2\nUncertainty principle satisfied")
        else:
            self.uncertainty_verdict.setStyleSheet(
                "font-weight: 800; font-size: 12px; margin-top: 8px; color: #dc2626;"
            )
            self.uncertainty_verdict.setText("✗ Δx·Δp < ħ/2\nShould never happen — check inputs")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuantumLab — Quantum Wave Packet")
        self.resize(1250, 820)
        self.setCentralWidget(WavePacketView())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()