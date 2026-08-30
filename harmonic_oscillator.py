"""
QUANTUM HARMONIC OSCILLATOR — Module 2

V(x) = 1/2 * m * omega^2 * x^2
E_n  = hbar * omega * (n + 1/2)
psi_n(x) uses the physicists' Hermite polynomials H_n, built here via
their recurrence relation (no scipy dependency needed):
    H_0(x) = 1
    H_1(x) = 2x
    H_n(x) = 2x*H_(n-1)(x) - 2(n-1)*H_(n-2)(x)

Run:
    pip install numpy matplotlib PyQt5
    python harmonic_oscillator.py
"""

import sys
import math
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QSlider, QRadioButton, QButtonGroup, QCheckBox,
    QGroupBox,
)
from PyQt5.QtCore import Qt


# =====================================================================
# PHYSICS — Quantum Harmonic Oscillator
# Natural units: hbar = 1. Mass m = 1 (kept fixed, per the plan — only
# omega is exposed as a control for this first version).
# =====================================================================

HBAR = 1.0
MASS = 1.0
MIN_N = 0
MAX_N = 10


def hermite(n, x):
    """Physicists' Hermite polynomial H_n(x), via recurrence."""
    H_prev2 = np.ones_like(x)
    if n == 0:
        return H_prev2
    H_prev1 = 2 * x
    if n == 1:
        return H_prev1
    for k in range(2, n + 1):
        H_curr = 2 * x * H_prev1 - 2 * (k - 1) * H_prev2
        H_prev2, H_prev1 = H_prev1, H_curr
    return H_prev1


def wavefunction(n, x, omega, m=MASS, hbar=HBAR):
    """psi_n(x) for the quantum harmonic oscillator."""
    xi = np.sqrt(m * omega / hbar) * x
    prefactor = (m * omega / (np.pi * hbar)) ** 0.25 / np.sqrt(2 ** n * math.factorial(n))
    return prefactor * hermite(n, xi) * np.exp(-xi ** 2 / 2)


def probability_density(n, x, omega, m=MASS, hbar=HBAR):
    return wavefunction(n, x, omega, m, hbar) ** 2


def energy(n, omega, hbar=HBAR):
    return hbar * omega * (n + 0.5)


def potential(x, omega, m=MASS):
    return 0.5 * m * omega ** 2 * x ** 2


def turning_points(n, omega, m=MASS, hbar=HBAR):
    """Classical turning points: where E_n = V(x)."""
    e = energy(n, omega, hbar)
    x_t = np.sqrt(2 * e / (m * omega ** 2))
    return -x_t, x_t


def nodes(n):
    """Number of nodes in psi_n — equals n for the harmonic oscillator."""
    return n


def parity(n):
    return "Even" if n % 2 == 0 else "Odd"


def check_normalization(n, x, omega, m=MASS, hbar=HBAR):
    return np.trapezoid(probability_density(n, x, omega, m, hbar), x)


def find_node_positions(n, x, omega, m=MASS, hbar=HBAR):
    """
    Interior zero crossings of psi_n(x), found by locating sign changes
    in the sampled array and linearly interpolating to the crossing
    point. Used only for the "Show nodes" markers.
    """
    psi = wavefunction(n, x, omega, m, hbar)
    signs = np.sign(psi)
    sign_changes = np.where(np.diff(signs) != 0)[0]
    positions = []
    for i in sign_changes:
        x0, x1 = x[i], x[i + 1]
        y0, y1 = psi[i], psi[i + 1]
        # Linear interpolation for the zero crossing between the two samples.
        x_zero = x0 - y0 * (x1 - x0) / (y1 - y0)
        positions.append(x_zero)
    return positions


def expectation_x(n, x, omega, m=MASS, hbar=HBAR):
    """<x> for eigenstate n — exactly 0 by symmetry, computed here
    numerically as a sanity check rather than assumed."""
    prob = probability_density(n, x, omega, m, hbar)
    return np.trapezoid(x * prob, x)


# =====================================================================
# Matplotlib-in-Qt canvas
# =====================================================================

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)


OMEGA_MIN_TENTHS = 5
OMEGA_MAX_TENTHS = 20
OMEGA_DEFAULT_TENTHS = 10


class HarmonicOscillatorView(QWidget):
    def __init__(self):
        super().__init__()
        self.n = 3
        self.omega = OMEGA_DEFAULT_TENTHS / 10
        self.display_mode = "psi"  # "psi", "prob", or "both"
        self.show_levels = True
        self.show_turning_points = True
        self.show_nodes = False

        self._build_ui()
        self._refresh()

    # -----------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        self.setStyleSheet("""
            QWidget {
                background-color: #080b11;
                color: #e7edf5;
            }
            QGroupBox {
                border: 1px solid #1e2a3a;
                border-radius: 10px;
                margin-top: 12px;
                padding: 10px 8px 8px 8px;
                background-color: #0b1119;
                font-weight: 600;
                color: #e7edf5;
                font-size: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #5fd98a;
                font-size: 16px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e2a3a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qradialgradient(cx:0.4, cy:0.4, radius:0.8,
                            fx:0.4, fy:0.4, stop:0 #f5b642, stop:1 #f59e0b);
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
                border: 1px solid #f5b642;
            }
            QSlider::sub-page:horizontal {
                background: #5fd98a;
                border-radius: 3px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox::indicator:checked {
                background-color: #5fd98a;
                border: 1px solid #5fd98a;
                border-radius: 3px;
            }
            QRadioButton::indicator:checked {
                background-color: #5fd98a;
                border: 1px solid #5fd98a;
                border-radius: 7px;
            }
            QLabel {
                color: #e7edf5;
                font-size: 14px;
            }
        """)

        root.addWidget(self._build_controls())
        root.addLayout(self._build_main_row())

    def _build_controls(self):
        box = QGroupBox("Controls")
        outer = QVBoxLayout(box)

        # --- n slider ---
        n_row = QHBoxLayout()
        self.n_label = QLabel(f"n = {self.n}")
        self.n_label.setFixedWidth(50)
        self.n_label.setStyleSheet("font-weight: bold;")
        self.n_slider = QSlider(Qt.Horizontal)
        self.n_slider.setMinimum(MIN_N)
        self.n_slider.setMaximum(MAX_N)
        self.n_slider.setValue(self.n)
        self.n_slider.setTickPosition(QSlider.TicksBelow)
        self.n_slider.setTickInterval(1)
        self.n_slider.valueChanged.connect(self._on_n_changed)
        n_row.addWidget(QLabel("Quantum number"))
        n_row.addWidget(self.n_label)
        n_row.addWidget(self.n_slider)
        outer.addLayout(n_row)

        # --- omega slider ---
        omega_row = QHBoxLayout()
        self.omega_label = QLabel(f"ω = {self.omega:.1f}")
        self.omega_label.setFixedWidth(60)
        self.omega_label.setStyleSheet("font-weight: bold;")
        self.omega_slider = QSlider(Qt.Horizontal)
        self.omega_slider.setMinimum(OMEGA_MIN_TENTHS)
        self.omega_slider.setMaximum(OMEGA_MAX_TENTHS)
        self.omega_slider.setValue(OMEGA_DEFAULT_TENTHS)
        self.omega_slider.setTickPosition(QSlider.TicksBelow)
        self.omega_slider.setTickInterval(1)
        self.omega_slider.valueChanged.connect(self._on_omega_changed)
        omega_row.addWidget(QLabel("Angular frequency"))
        omega_row.addWidget(self.omega_label)
        omega_row.addWidget(self.omega_slider)
        outer.addLayout(omega_row)

        # --- display mode + checkboxes ---
        options_row = QHBoxLayout()

        self.psi_radio = QRadioButton("ψ(x)")
        self.prob_radio = QRadioButton("|ψ(x)|²")
        self.both_radio = QRadioButton("Both")
        self.psi_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        for rb in (self.psi_radio, self.prob_radio, self.both_radio):
            mode_group.addButton(rb)
            rb.toggled.connect(self._on_display_mode_changed)

        self.levels_checkbox = QCheckBox("Energy levels")
        self.levels_checkbox.setChecked(True)
        self.levels_checkbox.stateChanged.connect(self._on_levels_toggle)

        self.turning_checkbox = QCheckBox("Turning points")
        self.turning_checkbox.setChecked(True)
        self.turning_checkbox.stateChanged.connect(self._on_turning_toggle)

        self.nodes_checkbox = QCheckBox("Show nodes")
        self.nodes_checkbox.setChecked(False)
        self.nodes_checkbox.stateChanged.connect(self._on_nodes_toggle)

        options_row.addWidget(QLabel("Display:"))
        options_row.addWidget(self.psi_radio)
        options_row.addWidget(self.prob_radio)
        options_row.addWidget(self.both_radio)
        options_row.addStretch()
        options_row.addWidget(self.levels_checkbox)
        options_row.addWidget(self.turning_checkbox)
        options_row.addWidget(self.nodes_checkbox)
        outer.addLayout(options_row)

        # --- Probability interpretation note (educational, always visible) ---
        interp_label = QLabel(
            "Probability density: |ψ(x)|²  —  higher |ψ|² means a greater "
            "probability of finding the particle there."
        )
        interp_label.setWordWrap(True)
        interp_label.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        outer.addWidget(interp_label)

        return box

    def _build_main_row(self):
        row = QHBoxLayout()

        self.canvas = MplCanvas(width=8, height=6)
        row.addWidget(self.canvas, stretch=3)

        info_panel = self._build_info_panel()
        info_panel.setMinimumWidth(230)
        row.addWidget(info_panel, stretch=2)

        return row

    def _build_info_panel(self):
        box = QGroupBox("Quantum State")
        layout = QGridLayout(box)

        def value_label():
            lbl = QLabel("—")
            lbl.setStyleSheet("font-weight: bold;")
            return lbl

        rows = ["n", "Energy", "Nodes", "Parity", "x₋", "x₊", "Normalization", "Wavefunction"]
        self.info_values = {}
        for i, name in enumerate(rows):
            layout.addWidget(QLabel(name), i, 0)
            val = value_label()
            if name == "Wavefunction":
                val.setWordWrap(True)
                val.setMinimumWidth(150)
            self.info_values[name] = val
            layout.addWidget(val, i, 1)

        next_row = len(rows)
        expectation_header = QLabel("Expectation values")
        expectation_header.setStyleSheet(
            "font-weight: bold; color: #7c3aed; margin-top: 8px;"
        )
        layout.addWidget(expectation_header, next_row, 0, 1, 2)
        next_row += 1

        for name in ["⟨x⟩", "⟨p⟩"]:
            layout.addWidget(QLabel(name), next_row, 0)
            val = value_label()
            self.info_values[name] = val
            layout.addWidget(val, next_row, 1)
            next_row += 1

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #64748b; font-style: italic; margin-top: 8px;")
        layout.addWidget(self.status_label, next_row, 0, 1, 2)
        next_row += 1

        layout.setRowStretch(next_row, 1)
        return box

    # -----------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------
    def _on_n_changed(self, value):
        self.n = value
        self.n_label.setText(f"n = {value}")
        self._refresh()

    def _on_omega_changed(self, value_tenths):
        self.omega = value_tenths / 10
        self.omega_label.setText(f"ω = {self.omega:.1f}")
        self._refresh()

    def _on_display_mode_changed(self):
        if self.psi_radio.isChecked():
            self.display_mode = "psi"
        elif self.prob_radio.isChecked():
            self.display_mode = "prob"
        else:
            self.display_mode = "both"
        self._refresh()

    def _on_levels_toggle(self, state):
        self.show_levels = bool(state)
        self._refresh()

    def _on_turning_toggle(self, state):
        self.show_turning_points = bool(state)
        self._refresh()

    def _on_nodes_toggle(self, state):
        self.show_nodes = bool(state)
        self._refresh()

    # -----------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------
    def _refresh(self):
        self._draw_plot()
        self._update_info_panel()
        self.canvas.draw_idle()

    def _draw_plot(self):
        ax = self.canvas.axes
        ax.clear()
        self.canvas.fig.set_facecolor("#ffffff")
        ax.set_facecolor("#fafaf9")
        ax.grid(True, color="#e2e8f0", linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color("#94a3b8")

        # x-range wide enough to comfortably show the highest energy
        # level's turning points, regardless of which n is selected —
        # keeps the ladder visually consistent as n changes.
        _, x_max_ref = turning_points(MAX_N, self.omega)
        x_max = x_max_ref * 1.3
        x = np.linspace(-x_max, x_max, 800)

        # --- Potential V(x) ---
        V = potential(x, self.omega)
        ax.plot(x, V, color="#334155", lw=2.2, label="V(x)", zorder=3)
        ax.fill_between(x, 0, V, color="#94a3b8", alpha=0.06, zorder=0)

        e_n = energy(self.n, self.omega)

        # --- Energy level ladder ---
        # Unselected levels are drawn very faint/dotted so they read as
        # background context; the selected level is bold and solid so
        # it's immediately obvious which state is being explored.
        if self.show_levels:
            for k in range(MIN_N, MAX_N + 1):
                e_k = energy(k, self.omega)
                if e_k > energy(MAX_N, self.omega) * 1.05:
                    continue
                is_active = k == self.n
                color = "#7c3aed" if is_active else "#e2e8f0"
                lw = 2.5 if is_active else 0.7
                _, xt = turning_points(k, self.omega)
                span = xt * 1.15
                if is_active:
                    # Soft glow behind the selected level — a couple of
                    # wider, lower-alpha lines underneath the crisp one.
                    ax.hlines(e_k, -span, span, color="#c4b5fd", lw=7, alpha=0.25, zorder=2)
                    ax.hlines(e_k, -span, span, color="#c4b5fd", lw=4, alpha=0.35, zorder=2)
                ax.hlines(e_k, -span, span, color=color, lw=lw,
                           linestyle="-" if is_active else (0, (1, 2)),
                           alpha=1.0 if is_active else 0.8, zorder=1 if not is_active else 3)
                ax.text(span * 1.03, e_k, f"n={k}", fontsize=7, va="center",
                         color=color if is_active else "#cbd5e1",
                         fontweight="bold" if is_active else "normal")
            # One proxy entry for the legend, representing the ladder as a whole.
            ax.plot([], [], color="#cbd5e1", linestyle=(0, (1, 2)), lw=1, label="Energy levels")

        # --- Wavefunction / probability density riding on its level ---
        # Purely a display convention (not physics): each curve is
        # vertically shifted to sit at height E_n, and scaled so its
        # oscillations use most of the vertical room before the next
        # level, without the two curves' shapes becoming hard to tell
        # apart when both are shown together.
        psi = wavefunction(self.n, x, self.omega)
        prob = psi ** 2

        level_gap = HBAR * self.omega
        psi_scale = 0.55 * level_gap / np.max(np.abs(psi)) if np.max(np.abs(psi)) > 0 else 1
        prob_scale = 0.5 * level_gap / np.max(prob) if np.max(prob) > 0 else 1

        if self.display_mode in ("psi", "both"):
            y = e_n + psi * psi_scale
            ax.plot(x, y, color="#7c3aed", lw=2.2, linestyle="-",
                     label=f"ψ_{self.n}(x)", zorder=4)
            ax.fill_between(x, e_n, y, color="#7c3aed", alpha=0.12, zorder=2)

        if self.display_mode in ("prob", "both"):
            y = e_n + prob * prob_scale
            ax.plot(x, y, color="#06b6d4", lw=2.2, linestyle="--",
                     label=f"|ψ_{self.n}(x)|²", zorder=4)
            ax.fill_between(x, e_n, y, color="#06b6d4", alpha=0.18, zorder=2)

        # --- Node markers ---
        # Small markers at the interior zeros of psi_n — lets the user
        # visually count and verify that a state with quantum number n
        # really does have exactly n nodes.
        if self.show_nodes:
            node_x = find_node_positions(self.n, x, self.omega)
            if node_x:
                ax.scatter(node_x, [e_n] * len(node_x), marker="x", s=55,
                            color="#334155", linewidths=1.6, zorder=6,
                            label=f"Nodes ({len(node_x)})")

        # --- Classically allowed region ---
        # Shaded band + a labeled double-headed arrow showing where
        # E_n > V(x) — the region a classical oscillator with this
        # energy would be confined to. Kept deliberately subtle (low
        # alpha, muted color, low zorder) so it reads as background
        # context rather than the first thing the eye is drawn to —
        # the intended visual hierarchy is wavefunction > energy level
        # > turning points > this shading.
        x_minus, x_plus = turning_points(self.n, self.omega)
        ax.axvspan(x_minus, x_plus, color="#eab308", alpha=0.05, zorder=0)

        arrow_y = potential(x_minus, self.omega) + energy(MAX_N, self.omega) * 0.035
        ax.annotate("", xy=(x_plus, arrow_y), xytext=(x_minus, arrow_y),
                     arrowprops=dict(arrowstyle="<->", color="#a8a29e", lw=0.8, alpha=0.7))
        ax.text((x_minus + x_plus) / 2, arrow_y, "classically allowed region",
                 ha="center", va="bottom", fontsize=6, color="#a8a29e", alpha=0.8)

        # --- Turning points ---
        # Labels sit near the very top of the plot with a thin dotted
        # connector down to the actual point, and are pushed outward
        # (left/right) so they clear the wavefunction and the ladder's
        # "n=" labels rather than sitting directly above the point.
        if self.show_turning_points:
            y_top = energy(MAX_N, self.omega) * 1.14
            ax.plot([x_minus, x_plus], [e_n, e_n], marker="o",
                     color="#ef4444", linestyle="None", markersize=5, zorder=5)
            ax.annotate(
                f"x₋ = {x_minus:.3f}",
                xy=(x_minus, e_n), xytext=(x_minus - 0.35, y_top),
                ha="right", va="top", fontsize=7, color="#ef4444",
                arrowprops=dict(arrowstyle="-", color="#ef4444", lw=0.8, linestyle=":"),
            )
            ax.annotate(
                f"x₊ = {x_plus:.3f}",
                xy=(x_plus, e_n), xytext=(x_plus + 0.35, y_top),
                ha="left", va="top", fontsize=7, color="#ef4444",
                arrowprops=dict(arrowstyle="-", color="#ef4444", lw=0.8, linestyle=":"),
            )

        ax.set_xlim(-x_max, x_max * 1.3)
        ax.set_ylim(0, energy(MAX_N, self.omega) * 1.22)
        ax.set_xlabel("x")
        ax.set_ylabel("Energy")
        ax.set_title(f"Quantum Harmonic Oscillator — ω = {self.omega:.1f}")
        ax.legend(loc="upper left", fontsize=7, framealpha=0.92,
                   fancybox=True, edgecolor="#e2e8f0")

    def _update_info_panel(self):
        e_n = energy(self.n, self.omega)
        x_minus, x_plus = turning_points(self.n, self.omega)

        _, x_max_ref = turning_points(MAX_N, self.omega)
        x_norm = np.linspace(-x_max_ref * 2, x_max_ref * 2, 2000)
        norm_value = check_normalization(self.n, x_norm, self.omega)

        self.info_values["n"].setText(str(self.n))
        self.info_values["Energy"].setText(f"{e_n:.3f}  (= {self.n} + 1/2) ħω")
        self.info_values["Nodes"].setText(str(nodes(self.n)))
        self.info_values["Parity"].setText(parity(self.n))
        self.info_values["x₋"].setText(f"{x_minus:.3f}")
        self.info_values["x₊"].setText(f"{x_plus:.3f}")

        is_ok = abs(norm_value - 1.0) < 0.01
        color = "#10b981" if is_ok else "#ef4444"
        mark = "✓" if is_ok else "✗"
        self.info_values["Normalization"].setText(f"{norm_value:.4f} {mark}")
        self.info_values["Normalization"].setStyleSheet(f"font-weight: bold; color: {color};")

        self.info_values["Wavefunction"].setText(
            f"ψ_{self.n}(x) ∝ H_{self.n}(ξ)\n        × e^(-ξ²/2)"
        )

        # --- Expectation values ---
        # <x> = 0 always for these eigenstates (the probability density
        # is symmetric or antisymmetric about x=0) — computed
        # numerically here as a verification rather than hard-coded.
        x_ev = expectation_x(self.n, x_norm, self.omega)
        self.info_values["⟨x⟩"].setText(f"{x_ev:.4f}")

        # <p> = 0 exactly for any real-valued wavefunction: <p> reduces
        # to (hbar/2i) * [psi^2] evaluated at the boundaries, which
        # vanishes since psi -> 0 as x -> +/- infinity. No numerical
        # integration needed — it's a direct consequence of psi being
        # real, not something special to this potential.
        self.info_values["⟨p⟩"].setText("0  (exact, ψ real)")

        node_word = "node" if nodes(self.n) == 1 else "nodes"
        if parity(self.n) == "Even":
            parity_explanation = "Even parity: ψ(x) is symmetric about x = 0."
        else:
            parity_explanation = "Odd parity: ψ(x) changes sign across x = 0."
        self.status_label.setText(
            f"State n = {self.n} — {nodes(self.n)} {node_word}, "
            f"{parity(self.n).lower()} parity.\n"
            f"{parity_explanation}\n"
            f"Higher n → more nodes."
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuantumLab — Quantum Harmonic Oscillator")
        self.resize(1150, 700)
        self.setCentralWidget(HarmonicOscillatorView())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    