"""
QUANTUM MECHANICS VISUALIZER
Particle in an Infinite Square Well.

Three physically-connected panels:
    V(x)  -->  |psi_n(x)|^2 (or psi_n(x))  -->  E_n

Run:
    pip install numpy matplotlib PyQt5
    python quantum_mechanics_visualizer.py
"""

import sys
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QSlider, QRadioButton, QButtonGroup, QCheckBox,
    QPushButton, QStackedWidget, QGroupBox,
)
from PyQt5.QtCore import Qt


# =====================================================================
# PHYSICS — Particle in an infinite square well.
# Natural units: hbar = 1, mass = 1.
# =====================================================================

HBAR = 1.0
MASS = 1.0
MIN_N = 1
MAX_N = 10


def wavefunction(n, x, L):
    return np.sqrt(2 / L) * np.sin(n * np.pi * x / L)


def probability_density(n, x, L):
    return wavefunction(n, x, L) ** 2


def energy(n, L, hbar=HBAR, m=MASS):
    return (n ** 2 * np.pi ** 2 * hbar ** 2) / (2 * m * L ** 2)


def energy_levels(n_max, L):
    return energy(np.arange(1, n_max + 1), L)


def check_normalization(n, x, L):
    return np.trapezoid(probability_density(n, x, L), x)


# =====================================================================
# Matplotlib-in-Qt canvas
# =====================================================================

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, width=4, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)


COMPARE_COLORS = [
    "#7c3aed", "#06b6d4", "#f59e0b", "#ef4444",
    "#10b981", "#3b82f6", "#ec4899", "#84cc16",
    "#f97316", "#8b5cf6",
]

L_MIN_TENTHS = 5
L_MAX_TENTHS = 20
L_DEFAULT_TENTHS = 10


class QuantumVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                background-color: #080b11;
                color: #e7edf5;
            }
            QGroupBox {
                border: 1px solid #1e2a3a;
                border-radius: 10px;
                margin-top: 12px;
                padding: 8px;
                background-color: #0b1119;
                color: #e7edf5;
                font-weight: 600;
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
                height: 6px; background: #1e2a3a; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qradialgradient(cx:0.4, cy:0.4, radius:0.8,
                            fx:0.4, fy:0.4, stop:0 #f5b642, stop:1 #f59e0b);
                width: 16px; height: 16px; margin: -6px 0;
                border-radius: 8px; border: 1px solid #f5b642;
            }
            QSlider::sub-page:horizontal { background: #5fd98a; border-radius: 3px; }
            QLabel { color: #e7edf5; font-size: 14px; }
            QCheckBox::indicator { width: 14px; height: 14px; }
            QCheckBox::indicator:checked {
                background-color: #5fd98a; border: 1px solid #5fd98a; border-radius: 3px;
            }
            QPushButton {
                font-weight: 700; font-size: 14px;
                padding: 6px 14px; border-radius: 8px;
                border: 1px solid #5fd98a; color: #e7edf5; background: #0b1119;
            }
            QPushButton:hover { background: #1a2230; }
            QPushButton:pressed { background: #0f172a; }
        """)
        self.single_n = 1
        self.compare_n_values = {1, 2}
        self.L = L_DEFAULT_TENTHS / 10
        self.show_wavefunction = False  # False = |psi|^2, True = psi(x)

        self._build_ui()
        self._refresh_all()

    # -----------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        root.addWidget(self._build_mode_toggle())
        root.addWidget(self._build_mode_stack())
        root.addWidget(self._build_L_control())
        root.addLayout(self._build_graphs_row())
        root.addLayout(self._build_bottom_row())

    def _build_mode_toggle(self):
        box = QGroupBox("Mode")
        layout = QHBoxLayout(box)
        self.single_radio = QRadioButton("Single state")
        self.compare_radio = QRadioButton("Compare states")
        self.single_radio.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.single_radio)
        group.addButton(self.compare_radio)
        self.single_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.single_radio)
        layout.addWidget(self.compare_radio)
        layout.addStretch()
        return box

    def _build_mode_stack(self):
        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_single_controls())
        self.mode_stack.addWidget(self._build_compare_controls())
        return self.mode_stack

    def _build_single_controls(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        self.n_label = QLabel(f"n = {self.single_n}")
        self.n_label.setFixedWidth(50)
        self.n_label.setStyleSheet("font-weight: bold;")
        self.n_slider = QSlider(Qt.Horizontal)
        self.n_slider.setMinimum(MIN_N)
        self.n_slider.setMaximum(MAX_N)
        self.n_slider.setValue(self.single_n)
        self.n_slider.setTickPosition(QSlider.TicksBelow)
        self.n_slider.setTickInterval(1)
        self.n_slider.valueChanged.connect(self._on_single_n_changed)
        layout.addWidget(self.n_label)
        layout.addWidget(self.n_slider)
        return widget

    def _build_compare_controls(self):
        widget = QWidget()
        outer = QVBoxLayout(widget)
        grid = QGridLayout()
        self.compare_checkboxes = {}
        for i, n in enumerate(range(MIN_N, MAX_N + 1)):
            cb = QCheckBox(f"n = {n}")
            cb.setChecked(n in self.compare_n_values)
            cb.stateChanged.connect(self._on_compare_changed)
            self.compare_checkboxes[n] = cb
            grid.addWidget(cb, i // 5, i % 5)
        outer.addLayout(grid)
        buttons_row = QHBoxLayout()
        select_all_btn = QPushButton("Select all")
        clear_all_btn = QPushButton("Clear all")
        select_all_btn.clicked.connect(self._select_all_compare)
        clear_all_btn.clicked.connect(self._clear_all_compare)
        buttons_row.addWidget(select_all_btn)
        buttons_row.addWidget(clear_all_btn)
        buttons_row.addStretch()
        outer.addLayout(buttons_row)
        return widget

    def _build_L_control(self):
        box = QGroupBox("Box length L")
        layout = QHBoxLayout(box)
        self.L_label = QLabel(f"L = {self.L:.1f}")
        self.L_label.setFixedWidth(60)
        self.L_label.setStyleSheet("font-weight: bold;")
        self.L_slider = QSlider(Qt.Horizontal)
        self.L_slider.setMinimum(L_MIN_TENTHS)
        self.L_slider.setMaximum(L_MAX_TENTHS)
        self.L_slider.setValue(L_DEFAULT_TENTHS)
        self.L_slider.setTickPosition(QSlider.TicksBelow)
        self.L_slider.setTickInterval(1)
        self.L_slider.valueChanged.connect(self._on_L_changed)
        layout.addWidget(self.L_label)
        layout.addWidget(self.L_slider)
        return box

    def _build_graphs_row(self):
        row = QHBoxLayout()

        # --- Left: the potential well V(x) ---
        well_col = QVBoxLayout()
        well_col.addWidget(QLabel("Potential  V(x)"))
        self.well_canvas = MplCanvas(width=3.2, height=4)
        well_col.addWidget(self.well_canvas)
        row.addLayout(well_col, stretch=2)

        # --- Middle: wavefunction / probability density, with toggle ---
        wave_col = QVBoxLayout()
        self.wave_toggle = QCheckBox("Show wavefunction ψₙ(x)")
        self.wave_toggle.stateChanged.connect(self._on_wave_toggle)
        wave_col.addWidget(self.wave_toggle)
        self.wave_canvas = MplCanvas(width=4.5, height=4)
        self.wave_canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        wave_col.addWidget(self.wave_canvas)
        row.addLayout(wave_col, stretch=3)

        # --- Right: energy level diagram ---
        energy_col = QVBoxLayout()
        energy_col.addWidget(QLabel("Energy levels  Eₙ"))
        self.energy_canvas = MplCanvas(width=3, height=4)
        energy_col.addWidget(self.energy_canvas)
        row.addLayout(energy_col, stretch=2)

        return row

    def _build_bottom_row(self):
        row = QHBoxLayout()

        self.normalization_label = QLabel("Normalization: —")
        self.normalization_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        row.addWidget(self.normalization_label)

        row.addStretch()

        self.coords_label = QLabel("(x, y) = (—, —)")
        self.coords_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #475569;")
        row.addWidget(self.coords_label)

        return row

    # -----------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------
    def _on_mode_changed(self):
        self.mode_stack.setCurrentIndex(0 if self.single_radio.isChecked() else 1)
        self._refresh_all()

    def _on_single_n_changed(self, value):
        self.single_n = value
        self.n_label.setText(f"n = {value}")
        self._refresh_all()

    def _on_compare_changed(self):
        self.compare_n_values = {
            n for n, cb in self.compare_checkboxes.items() if cb.isChecked()
        }
        self._refresh_all()

    def _on_wave_toggle(self, state):
        self.show_wavefunction = bool(state)
        self._refresh_all()

    def _on_L_changed(self, value_tenths):
        self.L = value_tenths / 10
        self.L_label.setText(f"L = {self.L:.1f}")
        self._refresh_all()

    def _select_all_compare(self):
        for cb in self.compare_checkboxes.values():
            cb.setChecked(True)

    def _clear_all_compare(self):
        for cb in self.compare_checkboxes.values():
            cb.setChecked(False)

    def _on_mouse_move(self, event):
        if event.xdata is None or event.ydata is None:
            self.coords_label.setText("(x, y) = (—, —)")
        else:
            self.coords_label.setText(f"(x, y) = ({event.xdata:.3f}, {event.ydata:.3f})")

    # -----------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------
    def _active_n_values(self):
        if self.single_radio.isChecked():
            return [self.single_n]
        return sorted(self.compare_n_values)

    def _refresh_all(self):
        self._draw_potential_well()
        self._draw_wave_plot()
        self._draw_energy_diagram()
        self._update_normalization()
        self.well_canvas.draw_idle()
        self.wave_canvas.draw_idle()
        self.energy_canvas.draw_idle()

    def _draw_potential_well(self):
        """
        V(x) = 0        for 0 < x < L
        V(x) = infinity  otherwise

        Drawn as: a flat zero line inside the well, and two vertical
        walls at x=0 and x=L rising off the top of the plot to
        represent the infinite potential barriers — the standard
        textbook sketch of an infinite square well.
        """
        ax = self.well_canvas.axes
        ax.clear()

        wall_top = 1.0  # visual height standing in for "infinity"
        margin = 0.15 * self.L

        # Flat V = 0 region inside the box
        ax.plot([0, self.L], [0, 0], color="#334155", lw=2.5)

        # Infinite walls at the boundaries
        ax.plot([0, 0], [0, wall_top], color="#334155", lw=2.5)
        ax.plot([self.L, self.L], [0, wall_top], color="#334155", lw=2.5)

        # Outside the well, V -> infinity: shaded regions
        ax.fill_betweenx([0, wall_top], -margin, 0, color="#cbd5e1", alpha=0.6)
        ax.fill_betweenx([0, wall_top], self.L, self.L + margin, color="#cbd5e1", alpha=0.6)

        ax.text(-margin / 2, wall_top * 0.8, "V = ∞", rotation=90,
                 ha="center", va="center", fontsize=9, color="#475569")
        ax.text(self.L + margin / 2, wall_top * 0.8, "V = ∞", rotation=90,
                 ha="center", va="center", fontsize=9, color="#475569")
        ax.text(self.L / 2, 0.08, "V = 0", ha="center", va="bottom",
                 fontsize=9, color="#334155")

        ax.set_xlim(-margin, self.L + margin)
        ax.set_ylim(-0.1, wall_top * 1.05)
        ax.set_xticks([0, self.L])
        ax.set_xticklabels(["0", "L"])
        ax.set_yticks([])
        ax.set_xlabel("x")
        ax.set_title("Infinite Square Well")

    def _draw_wave_plot(self):
        ax = self.wave_canvas.axes
        ax.clear()
        n_values = self._active_n_values()
        x = np.linspace(0, self.L, 500)

        if not n_values:
            ax.set_title("No states selected")
        else:
            for n in n_values:
                color = COMPARE_COLORS[(n - 1) % len(COMPARE_COLORS)]
                if self.show_wavefunction:
                    y = wavefunction(n, x, self.L)
                else:
                    y = probability_density(n, x, self.L)
                ax.plot(x / self.L, y, color=color, lw=2, label=f"n = {n}")

            ax.axhline(0, color="gray", lw=0.5)
            if len(n_values) > 1:
                ax.legend(loc="upper right", fontsize=8)

            title = "ψₙ(x)" if self.show_wavefunction else "|ψₙ(x)|²"
            ax.set_title(title)

        ax.set_xlabel("x / L")
        ax.set_ylabel("ψ(x)" if self.show_wavefunction else "|ψ(x)|²")
        peak = np.sqrt(2 / self.L)
        if self.show_wavefunction:
            ax.set_ylim(-peak * 1.15, peak * 1.15)
        else:
            ax.set_ylim(0, peak ** 2 * 1.15)

    def _draw_energy_diagram(self):
        ax = self.energy_canvas.axes
        ax.clear()
        levels = energy_levels(MAX_N, self.L)
        active = set(self._active_n_values())

        for n, e in zip(range(MIN_N, MAX_N + 1), levels):
            is_active = n in active
            color = COMPARE_COLORS[(n - 1) % len(COMPARE_COLORS)] if is_active else "#cbd5e1"
            lw = 2.5 if is_active else 1
            ax.hlines(e, 0, 1, color=color, lw=lw)
            ax.text(1.05, e, f"n={n}", va="center", fontsize=7,
                     color=color if is_active else "#94a3b8")

        ax.set_xlim(0, 1.6)
        ax.set_ylim(0, levels[-1] * 1.05)
        ax.set_xticks([])
        ax.set_ylabel("Energy (natural units)")
        ax.set_title(f"L = {self.L:.1f}")

    def _update_normalization(self):
        n_values = self._active_n_values()
        x = np.linspace(0, self.L, 500)
        if len(n_values) == 1:
            result = check_normalization(n_values[0], x, self.L)
            is_ok = abs(result - 1.0) < 0.01
            mark = "✓ Normalized" if is_ok else "✗ Not normalized"
            color = "#10b981" if is_ok else "#ef4444"
            self.normalization_label.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {color};"
            )
            self.normalization_label.setText(
                f"Normalization: ∫|ψ|² dx = {result:.4f}  {mark}"
            )
        else:
            self.normalization_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: gray;"
            )
            self.normalization_label.setText(
                "Normalization: (select a single state to check)"
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Mechanics Visualizer")
        self.resize(1200, 700)
        self.setCentralWidget(QuantumVisualizer())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()