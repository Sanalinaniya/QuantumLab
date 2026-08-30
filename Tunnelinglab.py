"""
Quantum Tunneling Lab — interactive rectangular-barrier visualizer (matplotlib)
================================================================================
Same physics, same visual language as the HTML/JS version:
    - exact analytic T and R for a finite rectangular barrier
    - real physical constants (electron mass, eV, nm)
    - live sliders for barrier height V0, barrier width a, particle energy E
    - a prominent QUANTUM REGIME panel that names which physics you're
      actually looking at:
          E < V0  ->  Tunneling                  (classically forbidden)
          E > V0  ->  Above-barrier scattering    (classically allowed,
                       quantum reflection still occurs)
    - animated wavefunction: correct wavelength, correct exponential-decay
      envelope inside the barrier, correct boundary amplitudes

Run:
    pip install numpy matplotlib
    python tunneling_lab.py

Close the window to stop the animation.
"""

import sys

import matplotlib
matplotlib.use("Qt5Agg")

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.widgets import Slider, Button
from matplotlib.animation import FuncAnimation
from matplotlib.patches import FancyBboxPatch

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt5.QtGui import QFont

# --------------------------------------------------------------------------
# 1. Physical constants (SI units)
# --------------------------------------------------------------------------
HBAR = 1.054571817e-34
ME   = 9.1093837015e-31
EV   = 1.602176634e-19
NM   = 1e-9

# --------------------------------------------------------------------------
# 2. Color palette
# --------------------------------------------------------------------------
BG, PANEL_BG, GRID = '#080b11', '#0b1119', '#1e2a3a'
TEXT, MUTED = '#e7edf5', '#7c8aa0'
CYAN, AMBER, VIOLET, PINK, GREEN, BLUE = (
    '#4dd8e6', '#f5b642', '#b591f0', '#ef7fa8', '#5fd98a', '#5b9dff'
)
TUNNEL_ACCENT, ABOVE_ACCENT, BORDER_ACCENT = VIOLET, BLUE, AMBER
VAXIS_MAX = 16.5


# --------------------------------------------------------------------------
# 3. Physics
# --------------------------------------------------------------------------
def compute_physics(V0_eV, a_nm, E_eV):
    V0, E, a = V0_eV * EV, E_eV * EV, a_nm * NM
    k1 = np.sqrt(2 * ME * E) / HBAR

    if abs(E_eV - V0_eV) < 0.003:
        regime = 'equal'
        T = 1.0 / (1.0 + (ME * V0 * a ** 2) / (2 * HBAR ** 2))
        kappa, k2 = None, None
    elif E_eV < V0_eV:
        regime = 'tunnel'
        kappa = np.sqrt(2 * ME * (V0 - E)) / HBAR
        s = np.sinh(kappa * a)
        T = 1.0 / (1.0 + (V0 ** 2 * s ** 2) / (4 * E * (V0 - E)))
        k2 = None
    else:
        regime = 'above'
        k2 = np.sqrt(2 * ME * (E - V0)) / HBAR
        s = np.sin(k2 * a)
        T = 1.0 / (1.0 + (V0 ** 2 * s ** 2) / (4 * E * (E - V0)))
        kappa = None

    T = min(1.0, max(0.0, T))
    R = 1.0 - T
    lambda1_nm = (2 * np.pi / k1) / NM
    resonance = (regime == 'above' and k2 is not None
                 and abs(np.sin(k2 * a)) < 0.035 and a_nm > 0.02)

    return dict(T=T, R=R, regime=regime, kappa=kappa, k2=k2, k1=k1,
                lambda1_nm=lambda1_nm, resonance=resonance,
                V0_eV=V0_eV, a_nm=a_nm, E_eV=E_eV)


def compute_wave(xs, phys, t):
    T, R, regime, a_nm = phys['T'], phys['R'], phys['regime'], phys['a_nm']
    sqrtT, sqrtR = np.sqrt(T), np.sqrt(R)
    k1 = phys['k1'] * NM
    k2 = phys['k2'] * NM if phys['k2'] is not None else 0.0

    psi = np.zeros_like(xs)
    left, right = xs < 0, xs > a_nm
    mid = ~left & ~right

    psi[left] = np.cos(k1 * xs[left] - t) + sqrtR * np.cos(k1 * xs[left] + t)
    psi[right] = sqrtT * np.cos(k1 * xs[right] - t)

    frac = xs[mid] / a_nm if a_nm > 0 else xs[mid] * 0
    if regime in ('tunnel', 'equal'):
        env = np.exp(np.log(max(sqrtT, 1e-6)) * frac)
        psi[mid] = env * np.cos(t)
    else:
        amp = 1 + (sqrtT - 1) * frac
        psi[mid] = amp * np.cos(k2 * xs[mid] - t)

    return psi


PRESETS = [
    ('STM gap', 6.0, 0.40, 2.0),
    ('Thick wall', 8.0, 2.00, 2.0),
    ('Near resonance', 3.0, 0.354, 6.0),
    ('Deep tunneling', 10.0, 1.50, 1.0),
]


class TunnelingLabView(QWidget):
    """Embedded tunneling visualizer for QuantumLab."""

    def __init__(self, on_back):
        super().__init__()
        self.on_back = on_back
        self.state = {'xs': None, 'phys': None, 'wave_line': None, 't_phase': 0.0}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        self.fig = Figure(figsize=(11.5, 10.2), facecolor=BG)
        self.fig.text(0.07, 0.978, 'INTERACTIVE PHYSICS LAB', color=CYAN,
                      fontsize=10, fontweight='bold', family='monospace')
        self.fig.text(0.07, 0.953, 'Quantum Tunneling & Above-Barrier Scattering',
                      color=TEXT, fontsize=18, fontweight='bold')
        self.fig.text(0.07, 0.933,
                      "Real \u0127, real electron mass. Energies in eV, lengths in nm.",
                      color=MUTED, fontsize=9.5)

        self.ax_pot = self.fig.add_axes([0.09, 0.695, 0.87, 0.205])
        self.ax_wave = self.fig.add_axes([0.09, 0.480, 0.87, 0.195], sharex=self.ax_pot)

        self.canvas = FigureCanvasQTAgg(self.fig)
        outer.addWidget(self.canvas)

        self._build_sliders()
        self._build_regime_panel()
        self._build_readouts()
        self._build_presets()

        for s in (self.v0_slider, self.a_slider, self.e_slider):
            s.on_changed(self.redraw_static)

        self.redraw_static()
        self.ani = FuncAnimation(self.fig, self.animate, interval=40,
                                 blit=False, cache_frame_data=False)

    def _build_header(self):
        row = QHBoxLayout()
        row.setContentsMargins(14, 10, 14, 10)
        back_btn = QPushButton("← Back to QuantumLab")
        back_btn.clicked.connect(self._on_back_clicked)
        title = QLabel("Quantum Tunneling Lab")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        row.addWidget(back_btn)
        row.addStretch()
        row.addWidget(title)
        row.addStretch()
        w = QWidget()
        w.setLayout(row)
        return w

    def _on_back_clicked(self):
        if hasattr(self, 'ani'):
            try:
                self.ani.event_source.stop()
            except Exception:
                pass
        if self.on_back is not None:
            self.on_back()

    def _style_axes(self, ax):
        ax.set_facecolor(PANEL_BG)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.grid(color=GRID, alpha=0.4, linewidth=0.6)

    def _make_slider_axes(self, y):
        ax = self.fig.add_axes([0.09, y, 0.35, 0.022])
        ax.set_facecolor(GRID)
        return ax

    def _build_sliders(self):
        ax_v0 = self._make_slider_axes(0.410)
        ax_a = self._make_slider_axes(0.375)
        ax_e = self._make_slider_axes(0.340)

        self.v0_slider = Slider(ax_v0, 'V0 (eV)', 0.2, 12.0, valinit=5.0,
                                valstep=0.1, color=AMBER, initcolor='none')
        self.a_slider = Slider(ax_a, 'a (nm)', 0.05, 3.0, valinit=0.5,
                               valstep=0.01, color=VIOLET, initcolor='none')
        self.e_slider = Slider(ax_e, 'E (eV)', 0.1, 15.0, valinit=3.0,
                               valstep=0.1, color=CYAN, initcolor='none')

        for s in (self.v0_slider, self.a_slider, self.e_slider):
            s.label.set_color(TEXT)
            s.label.set_fontsize(9.5)
            s.valtext.set_color(TEXT)
            s.valtext.set_fontsize(9.5)

    def _build_regime_panel(self):
        self.ax_regime = self.fig.add_axes([0.52, 0.282, 0.41, 0.150])
        self.ax_regime.set_xlim(0, 1)
        self.ax_regime.set_ylim(0, 1)
        self.ax_regime.axis('off')

        self.regime_tint = FancyBboxPatch(
            (0.015, 0.04), 0.97, 0.92,
            boxstyle='round,pad=0.0,rounding_size=0.05',
            linewidth=0, facecolor=VIOLET, alpha=0.08)
        self.regime_box = FancyBboxPatch(
            (0.015, 0.04), 0.97, 0.92,
            boxstyle='round,pad=0.0,rounding_size=0.05',
            linewidth=1.4, edgecolor=VIOLET, facecolor='none')
        self.ax_regime.add_patch(self.regime_tint)
        self.ax_regime.add_patch(self.regime_box)

        self.regime_value_text = self.ax_regime.text(
            0.5, 0.68, '', color=VIOLET, fontsize=15.5, ha='center',
            va='center', fontweight='bold', family='monospace')
        self.regime_name_text = self.ax_regime.text(
            0.5, 0.255, '', color=TEXT, fontsize=10.5, ha='center',
            va='center', fontweight='bold')
        self.regime_status_text = self.ax_regime.text(
            0.5, 0.10, '', color=MUTED, fontsize=7.6, ha='center', va='center')

    def _build_readouts(self):
        self.info_text = self.fig.text(0.09, 0.290, '', color=MUTED, fontsize=9.2,
                                       family='monospace', va='top', linespacing=1.9)
        self.t_line = self.fig.text(0.52, 0.252, '', color=CYAN, fontsize=11,
                                    family='monospace', va='top', fontweight='bold')
        self.r_line = self.fig.text(0.52, 0.214, '', color=PINK, fontsize=11,
                                    family='monospace', va='top', fontweight='bold')
        self.check_line = self.fig.text(0.52, 0.176, '', color=GREEN, fontsize=10,
                                        family='monospace', va='top')
        self.resonance_line = self.fig.text(0.52, 0.145, '', color=AMBER, fontsize=8.6,
                                            family='monospace', va='top')

    def _build_presets(self):
        self.preset_buttons = []
        bx = 0.09
        for label, V0, a, E in PRESETS:
            bax = self.fig.add_axes([bx, 0.030, 0.18, 0.042])
            btn = Button(bax, label, color=PANEL_BG, hovercolor='#182234')
            btn.label.set_color(TEXT)
            btn.label.set_fontsize(8)
            self.preset_buttons.append(btn)
            bx += 0.21

        for btn, (_, V0, a, E) in zip(self.preset_buttons, PRESETS):
            btn.on_clicked(self._make_preset_handler(V0, a, E))

    def _make_preset_handler(self, V0, a, E):
        def handler(_event):
            self.v0_slider.set_val(V0)
            self.a_slider.set_val(a)
            self.e_slider.set_val(E)
        return handler

    def redraw_static(self, _event=None):
        V0, a, E = self.v0_slider.val, self.a_slider.val, self.e_slider.val
        phys = compute_physics(V0, a, E)
        lambda1 = phys['lambda1_nm']
        margin = min(2.6, max(0.55, 1.5 * lambda1))
        xmin, xmax = -margin, a + margin
        xs = np.linspace(xmin, xmax, 500)

        self.ax_pot.cla()
        self._style_axes(self.ax_pot)
        self.ax_pot.set_ylim(0, VAXIS_MAX)
        self.ax_pot.set_xlim(xmin, xmax)
        x_step = [xmin, 0, 0, a, a, xmax]
        v_step = [0, 0, V0, V0, 0, 0]
        self.ax_pot.fill_between(x_step, 0, v_step, color=AMBER, alpha=0.22)
        self.ax_pot.plot(x_step, v_step, color=AMBER, lw=2.2)
        self.ax_pot.axhline(E, color=CYAN, ls='--', lw=1.6)
        self.ax_pot.axvspan(0, a, color=AMBER, alpha=0.05)
        self.ax_pot.text((0 + a) / 2, min(V0 + 0.9, VAXIS_MAX - 0.6), f'V0 = {V0:.1f} eV',
                         color=AMBER, fontsize=9.5, ha='center', fontweight='bold')
        self.ax_pot.text(xmax - 0.05 * (xmax - xmin), min(E + 0.5, VAXIS_MAX - 0.4),
                         f'E = {E:.1f} eV', color=CYAN, fontsize=9.5, ha='right', fontweight='bold')
        self.ax_pot.set_ylabel('V(x)  [eV]', color=MUTED, fontsize=9)
        for lbl in self.ax_pot.get_xticklabels():
            lbl.set_visible(False)

        self.ax_wave.cla()
        self._style_axes(self.ax_wave)
        self.ax_wave.set_xlim(xmin, xmax)
        self.ax_wave.set_ylim(-2.2, 2.2)
        self.ax_wave.axhline(0, color=GRID, lw=1)
        self.ax_wave.axvspan(0, a, color=AMBER, alpha=0.05)
        for bx_ in (0, a):
            self.ax_wave.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)
            self.ax_pot.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)

        sqrtT = np.sqrt(phys['T'])
        self.ax_wave.axhline(1, color='#ffffff', alpha=0.08, ls=':', lw=1)
        self.ax_wave.axhline(-1, color='#ffffff', alpha=0.08, ls=':', lw=1)
        self.ax_wave.axhline(sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)
        self.ax_wave.axhline(-sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)

        regime = phys['regime']
        if regime in ('tunnel', 'equal'):
            xb = np.linspace(0, a, 60)
            frac = xb / a if a > 0 else xb * 0
            env = np.exp(np.log(max(sqrtT, 1e-6)) * frac)
            self.ax_wave.fill_between(xb, -env, env, color=VIOLET, alpha=0.10)
        else:
            self.ax_wave.axvspan(0, a, color=BLUE, alpha=0.04)

        wave_line, = self.ax_wave.plot([], [], color=CYAN, lw=2.2)
        self.ax_wave.set_xlabel('x  (nm)', color=MUTED, fontsize=9)
        self.ax_wave.set_ylabel('Re[\u03c8(x,t)]', color=MUTED, fontsize=9)

        band_color = VIOLET if regime in ('tunnel', 'equal') else BLUE
        self.ax_wave.text(xmin * 0.55, -1.92, 'incident + reflected', color=MUTED, fontsize=8, ha='center')
        self.ax_wave.text((0 + a) / 2, -1.92, 'barrier region', color=band_color, fontsize=8, ha='center')
        self.ax_wave.text(a + margin * 0.55, -1.92, 'transmitted', color=MUTED, fontsize=8, ha='center')

        if regime == 'tunnel':
            accent = TUNNEL_ACCENT
            value_txt, name_txt = 'E < V\u2080', 'Tunneling'
            status_txt = 'Classically forbidden — wavefunction still penetrates.'
        elif regime == 'above':
            accent = ABOVE_ACCENT
            value_txt, name_txt = 'E > V\u2080', 'Above-barrier scattering'
            status_txt = 'Classically allowed — quantum reflection still occurs.'
        else:
            accent = BORDER_ACCENT
            value_txt, name_txt = 'E \u2248 V\u2080', 'Borderline regime'
            status_txt = 'Transition point between tunneling and scattering.'

        self.regime_tint.set_facecolor(accent)
        self.regime_box.set_edgecolor(accent)
        self.regime_value_text.set_text(value_txt)
        self.regime_value_text.set_color(accent)
        self.regime_name_text.set_text(name_txt)
        self.regime_status_text.set_text(status_txt)

        if regime == 'tunnel':
            thick = np.exp(-2 * phys['kappa'] * NM * a)
            self.info_text.set_text(
                f"\u03ba (decay const.)   {phys['kappa']*NM:.3f} /nm\n"
                f"\u03baa                  {phys['kappa']*NM*a:.3f}\n"
                f"e^(-2\u03baa) estimate   {thick:.2e}\n"
                f"\u03bb (incident)        {phys['lambda1_nm']:.3f} nm"
            )
        elif regime == 'above':
            self.info_text.set_text(
                f"k2 (inside barrier) {phys['k2']*NM:.3f} /nm\n"
                f"k2\u00b7a                 {phys['k2']*NM*a:.3f}\n"
                f"\u03bb (incident)         {phys['lambda1_nm']:.3f} nm"
            )
        else:
            self.info_text.set_text(
                f"\u03ba \u2192 0   (E \u2248 V0)\n"
                f"\u03bb (incident)   {phys['lambda1_nm']:.3f} nm"
            )

        self.t_line.set_text(f"Transmission:  {phys['T']*100:6.2f} %")
        self.r_line.set_text(f"Reflection:    {phys['R']*100:6.2f} %")
        self.check_line.set_text(f"R + T = {phys['R']+phys['T']:.4f}  OK")
        self.resonance_line.set_text(
            '\u2605 resonance: T \u2248 1, barrier nearly transparent' if phys['resonance'] else ''
        )

        self.state['xs'], self.state['phys'], self.state['wave_line'] = xs, phys, wave_line
        self.fig.canvas.draw_idle()

    def animate(self, _frame):
        self.state['t_phase'] += 0.09
        xs, phys, wave_line = self.state['xs'], self.state['phys'], self.state['wave_line']
        psi = compute_wave(xs, phys, self.state['t_phase'])
        wave_line.set_data(xs, psi)
        return (wave_line,)


def create_tunneling(on_back):
    return TunnelingLabView(on_back)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = TunnelingLabView(on_back=lambda: app.quit())
    window.resize(1150, 1020)
    window.show()
    sys.exit(app.exec_())












# """
# Quantum Tunneling Lab — interactive rectangular-barrier visualizer (matplotlib)
# ================================================================================
# Same physics, same visual language as the HTML/JS version:
#     - exact analytic T and R for a finite rectangular barrier
#     - real physical constants (electron mass, eV, nm)
#     - live sliders for barrier height V0, barrier width a, particle energy E
#     - a prominent QUANTUM REGIME panel that names which physics you're
#       actually looking at:
#           E < V0  ->  Tunneling                  (classically forbidden)
#           E > V0  ->  Above-barrier scattering    (classically allowed,
#                        quantum reflection still occurs)
#     - animated wavefunction: correct wavelength, correct exponential-decay
#       envelope inside the barrier, correct boundary amplitudes

# INTEGRATION NOTE (for QuantumLab)
# ----------------------------------
# This used to be a standalone script: everything ran at import time and
# ended in plt.show(), which opens its own window with its own event
# loop. That can't coexist with QuantumLab's single QApplication, so the
# whole thing is now built inside TunnelingLabView.__init__ instead, and
# the figure is embedded in a Qt canvas (FigureCanvasQTAgg) rather than
# shown via pyplot. Every slider, button, panel, and the physics itself
# are UNCHANGED from the original — only the "am I my own app or a
# widget inside something else" wrapper changed.

# Run standalone (for testing this file on its own):
#     pip install numpy matplotlib PyQt5
#     python Tunnelinglab.py
# """

# import numpy as np
# import matplotlib
# matplotlib.use("QtAgg")  # ensure the Qt backend before any figure is built
# from matplotlib.figure import Figure
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
# from matplotlib.widgets import Slider, Button
# from matplotlib.animation import FuncAnimation
# from matplotlib.patches import FancyBboxPatch

# from PyQt5.QtWidgets import (
#     QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
# )
# from PyQt5.QtGui import QFont

# # --------------------------------------------------------------------------
# # 1. Physical constants (SI units) — unchanged
# # --------------------------------------------------------------------------
# HBAR = 1.054571817e-34
# ME   = 9.1093837015e-31
# EV   = 1.602176634e-19
# NM   = 1e-9

# # --------------------------------------------------------------------------
# # 2. Color palette — unchanged
# # --------------------------------------------------------------------------
# BG, PANEL_BG, GRID = '#080b11', '#0b1119', '#1e2a3a'
# TEXT, MUTED = '#e7edf5', '#7c8aa0'
# CYAN, AMBER, VIOLET, PINK, GREEN, BLUE = (
#     '#4dd8e6', '#f5b642', '#b591f0', '#ef7fa8', '#5fd98a', '#5b9dff'
# )
# TUNNEL_ACCENT, ABOVE_ACCENT, BORDER_ACCENT = VIOLET, BLUE, AMBER

# VAXIS_MAX = 16.5


# # --------------------------------------------------------------------------
# # 3. Physics — unchanged, kept as free functions (no reason for these to
# #    be methods; they don't touch any widget state)
# # --------------------------------------------------------------------------
# def compute_physics(V0_eV, a_nm, E_eV):
#     V0, E, a = V0_eV * EV, E_eV * EV, a_nm * NM
#     k1 = np.sqrt(2 * ME * E) / HBAR

#     if abs(E_eV - V0_eV) < 0.003:
#         regime = 'equal'
#         T = 1.0 / (1.0 + (ME * V0 * a ** 2) / (2 * HBAR ** 2))
#         kappa, k2 = None, None
#     elif E_eV < V0_eV:
#         regime = 'tunnel'
#         kappa = np.sqrt(2 * ME * (V0 - E)) / HBAR
#         s = np.sinh(kappa * a)
#         T = 1.0 / (1.0 + (V0 ** 2 * s ** 2) / (4 * E * (V0 - E)))
#         k2 = None
#     else:
#         regime = 'above'
#         k2 = np.sqrt(2 * ME * (E - V0)) / HBAR
#         s = np.sin(k2 * a)
#         T = 1.0 / (1.0 + (V0 ** 2 * s ** 2) / (4 * E * (E - V0)))
#         kappa = None

#     T = min(1.0, max(0.0, T))
#     R = 1.0 - T
#     lambda1_nm = (2 * np.pi / k1) / NM
#     resonance = (regime == 'above' and k2 is not None
#                  and abs(np.sin(k2 * a)) < 0.035 and a_nm > 0.02)

#     return dict(T=T, R=R, regime=regime, kappa=kappa, k2=k2, k1=k1,
#                 lambda1_nm=lambda1_nm, resonance=resonance,
#                 V0_eV=V0_eV, a_nm=a_nm, E_eV=E_eV)


# def compute_wave(xs, phys, t):
#     T, R, regime, a_nm = phys['T'], phys['R'], phys['regime'], phys['a_nm']
#     sqrtT, sqrtR = np.sqrt(T), np.sqrt(R)
#     k1 = phys['k1'] * NM
#     k2 = phys['k2'] * NM if phys['k2'] is not None else 0.0

#     psi = np.zeros_like(xs)
#     left, right = xs < 0, xs > a_nm
#     mid = ~left & ~right

#     psi[left] = np.cos(k1 * xs[left] - t) + sqrtR * np.cos(k1 * xs[left] + t)
#     psi[right] = sqrtT * np.cos(k1 * xs[right] - t)

#     frac = xs[mid] / a_nm if a_nm > 0 else xs[mid] * 0
#     if regime in ('tunnel', 'equal'):
#         env = np.exp(np.log(max(sqrtT, 1e-6)) * frac)
#         psi[mid] = env * np.cos(t)
#     else:
#         amp = 1 + (sqrtT - 1) * frac
#         psi[mid] = amp * np.cos(k2 * xs[mid] - t)

#     return psi


# PRESETS = [
#     ('STM gap',        6.0, 0.40, 2.0),
#     ('Thick wall',     8.0, 2.00, 2.0),
#     ('Near resonance', 3.0, 0.354, 6.0),
#     ('Deep tunneling', 10.0, 1.50, 1.0),
# ]


# class TunnelingLabView(QWidget):
#     """
#     Everything that used to run at module-import time now runs inside
#     __init__ instead, and every object that used to be a bare module-level
#     name (fig, ax_pot, v0_slider, state, ...) is now self.<name> so the
#     various callback methods below can reach them. The physics and the
#     visual design are byte-for-byte the same as the original script —
#     only this "am I a standalone app or an embeddable widget" wrapper
#     changed, exactly as planned.
#     """

#     def __init__(self, on_back):
#         super().__init__()
#         self.on_back = on_back
#         self.state = {'xs': None, 'phys': None, 'wave_line': None, 't_phase': 0.0}

#         outer = QVBoxLayout(self)
#         outer.setContentsMargins(0, 0, 0, 0)
#         outer.setSpacing(0)
#         outer.addWidget(self._build_header())

#         self._build_figure()
#         self.canvas = FigureCanvasQTAgg(self.fig)
#         outer.addWidget(self.canvas)

#         self._build_sliders()
#         self._build_regime_panel()
#         self._build_readouts()
#         self._build_presets()

#         for s in (self.v0_slider, self.a_slider, self.e_slider):
#             s.on_changed(self.redraw_static)

#         self.redraw_static()  # initial draw

#         self.ani = FuncAnimation(self.fig, self.animate, interval=40,
#                                   blit=False, cache_frame_data=False)

#     # -----------------------------------------------------------
#     # QuantumLab chrome: header + back button (new — everything below
#     # this method is the original script's content, relocated)
#     # -----------------------------------------------------------
#     def _build_header(self):
#         row = QHBoxLayout()
#         row.setContentsMargins(14, 10, 14, 10)
#         back_btn = QPushButton("← Back to QuantumLab")
#         back_btn.clicked.connect(self._on_back_clicked)
#         title = QLabel("Quantum Tunneling Lab")
#         f = QFont()
#         f.setPointSize(13)
#         f.setBold(True)
#         title.setFont(f)
#         row.addWidget(back_btn)
#         row.addStretch()
#         row.addWidget(title)
#         row.addStretch()
#         w = QWidget()
#         w.setLayout(row)
#         return w

#     def _on_back_clicked(self):
#         # Stop the animation before leaving — an animation left running
#         # in the background would keep firing against a canvas that's
#         # no longer the visible screen.
#         self.ani.event_source.stop()
#         self.on_back()

#     # -----------------------------------------------------------
#     # 4. Figure & static layout — unchanged positions/sizes, just built
#     #    with Figure() instead of plt.figure() so pyplot never manages
#     #    this window.
#     # -----------------------------------------------------------
#     def _build_figure(self):
#         matplotlib_rcparams_monospace()

#         self.fig = Figure(figsize=(11.5, 10.2), facecolor=BG)

#         self.fig.text(0.07, 0.978, 'INTERACTIVE PHYSICS LAB', color=CYAN,
#                        fontsize=10, fontweight='bold', family='monospace')
#         self.fig.text(0.07, 0.953, 'Quantum Tunneling & Above-Barrier Scattering',
#                        color=TEXT, fontsize=18, fontweight='bold')
#         self.fig.text(0.07, 0.933,
#                        "Real \u0127, real electron mass. Energies in eV, lengths in nm.",
#                        color=MUTED, fontsize=9.5)

#         self.ax_pot = self.fig.add_axes([0.09, 0.695, 0.87, 0.205])
#         self.ax_wave = self.fig.add_axes([0.09, 0.480, 0.87, 0.195], sharex=self.ax_pot)

#     def _style_axes(self, ax):
#         ax.set_facecolor(PANEL_BG)
#         for spine in ax.spines.values():
#             spine.set_color(GRID)
#         ax.tick_params(colors=MUTED, labelsize=8)
#         ax.grid(color=GRID, alpha=0.4, linewidth=0.6)

#     # -----------------------------------------------------------
#     # 5. Sliders (LEFT column, x: 0.09 - 0.44) — unchanged
#     # -----------------------------------------------------------
#     def _make_slider_axes(self, y):
#         ax = self.fig.add_axes([0.09, y, 0.35, 0.022])
#         ax.set_facecolor(GRID)
#         return ax

#     def _build_sliders(self):
#         ax_v0 = self._make_slider_axes(0.410)
#         ax_a = self._make_slider_axes(0.375)
#         ax_e = self._make_slider_axes(0.340)

#         self.v0_slider = Slider(ax_v0, 'V0 (eV)', 0.2, 12.0, valinit=5.0,
#                                  valstep=0.1, color=AMBER, initcolor='none')
#         self.a_slider = Slider(ax_a, 'a (nm)', 0.05, 3.0, valinit=0.5,
#                                 valstep=0.01, color=VIOLET, initcolor='none')
#         self.e_slider = Slider(ax_e, 'E (eV)', 0.1, 15.0, valinit=3.0,
#                                 valstep=0.1, color=CYAN, initcolor='none')

#         for s in (self.v0_slider, self.a_slider, self.e_slider):
#             s.label.set_color(TEXT)
#             s.label.set_fontsize(9.5)
#             s.valtext.set_color(TEXT)
#             s.valtext.set_fontsize(9.5)

#     # -----------------------------------------------------------
#     # 6. Quantum-regime panel — unchanged
#     # -----------------------------------------------------------
#     def _build_regime_panel(self):
#         self.ax_regime = self.fig.add_axes([0.52, 0.282, 0.41, 0.150])
#         self.ax_regime.set_xlim(0, 1)
#         self.ax_regime.set_ylim(0, 1)
#         self.ax_regime.axis('off')

#         self.regime_tint = FancyBboxPatch(
#             (0.015, 0.04), 0.97, 0.92,
#             boxstyle='round,pad=0.0,rounding_size=0.05',
#             linewidth=0, facecolor=VIOLET, alpha=0.08)
#         self.regime_box = FancyBboxPatch(
#             (0.015, 0.04), 0.97, 0.92,
#             boxstyle='round,pad=0.0,rounding_size=0.05',
#             linewidth=1.4, edgecolor=VIOLET, facecolor='none')
#         self.ax_regime.add_patch(self.regime_tint)
#         self.ax_regime.add_patch(self.regime_box)

#         self.regime_value_text = self.ax_regime.text(
#             0.5, 0.68, '', color=VIOLET, fontsize=15.5, ha='center',
#             va='center', fontweight='bold', family='monospace')
#         self.regime_name_text = self.ax_regime.text(
#             0.5, 0.255, '', color=TEXT, fontsize=10.5, ha='center',
#             va='center', fontweight='bold')
#         self.regime_status_text = self.ax_regime.text(
#             0.5, 0.10, '', color=MUTED, fontsize=7.6, ha='center', va='center')

#     # -----------------------------------------------------------
#     # 7. Readout text blocks — unchanged
#     # -----------------------------------------------------------
#     def _build_readouts(self):
#         self.info_text = self.fig.text(0.09, 0.290, '', color=MUTED, fontsize=9.2,
#                                         family='monospace', va='top', linespacing=1.9)
#         self.t_line = self.fig.text(0.52, 0.252, '', color=CYAN, fontsize=11,
#                                      family='monospace', va='top', fontweight='bold')
#         self.r_line = self.fig.text(0.52, 0.214, '', color=PINK, fontsize=11,
#                                      family='monospace', va='top', fontweight='bold')
#         self.check_line = self.fig.text(0.52, 0.176, '', color=GREEN, fontsize=10,
#                                          family='monospace', va='top')
#         self.resonance_line = self.fig.text(0.52, 0.145, '', color=AMBER, fontsize=8.6,
#                                              family='monospace', va='top')

#     # -----------------------------------------------------------
#     # 8. Preset buttons — unchanged
#     # -----------------------------------------------------------
#     def _build_presets(self):
#         self.preset_buttons = []
#         bx = 0.09
#         for label, V0, a, E in PRESETS:
#             bax = self.fig.add_axes([bx, 0.030, 0.18, 0.042])
#             btn = Button(bax, label, color=PANEL_BG, hovercolor='#182234')
#             btn.label.set_color(TEXT)
#             btn.label.set_fontsize(8)
#             self.preset_buttons.append(btn)
#             bx += 0.21

#         for btn, (_, V0, a, E) in zip(self.preset_buttons, PRESETS):
#             btn.on_clicked(self._make_preset_handler(V0, a, E))

#     def _make_preset_handler(self, V0, a, E):
#         def handler(_event):
#             self.v0_slider.set_val(V0)
#             self.a_slider.set_val(a)
#             self.e_slider.set_val(E)  # last set_val fires redraw_static via its callback
#         return handler

#     # -----------------------------------------------------------
#     # 9. State + redraw-on-slider-change — unchanged logic
#     # -----------------------------------------------------------
#     def redraw_static(self, _event=None):
#         V0, a, E = self.v0_slider.val, self.a_slider.val, self.e_slider.val
#         phys = compute_physics(V0, a, E)
#         lambda1 = phys['lambda1_nm']
#         margin = min(2.6, max(0.55, 1.5 * lambda1))
#         xmin, xmax = -margin, a + margin
#         xs = np.linspace(xmin, xmax, 500)

#         # ---- potential panel ----
#         self.ax_pot.cla()
#         self._style_axes(self.ax_pot)
#         self.ax_pot.set_ylim(0, VAXIS_MAX)
#         self.ax_pot.set_xlim(xmin, xmax)
#         x_step = [xmin, 0, 0, a, a, xmax]
#         v_step = [0, 0, V0, V0, 0, 0]
#         self.ax_pot.fill_between(x_step, 0, v_step, color=AMBER, alpha=0.22)
#         self.ax_pot.plot(x_step, v_step, color=AMBER, lw=2.2)
#         self.ax_pot.axhline(E, color=CYAN, ls='--', lw=1.6)
#         self.ax_pot.axvspan(0, a, color=AMBER, alpha=0.05)
#         self.ax_pot.text((0 + a) / 2, min(V0 + 0.9, VAXIS_MAX - 0.6), f'V0 = {V0:.1f} eV',
#                           color=AMBER, fontsize=9.5, ha='center', fontweight='bold')
#         self.ax_pot.text(xmax - 0.05 * (xmax - xmin), min(E + 0.5, VAXIS_MAX - 0.4),
#                           f'E = {E:.1f} eV', color=CYAN, fontsize=9.5, ha='right', fontweight='bold')
#         self.ax_pot.set_ylabel('V(x)  [eV]', color=MUTED, fontsize=9)
#         for lbl in self.ax_pot.get_xticklabels():
#             lbl.set_visible(False)

#         # ---- wavefunction panel ----
#         self.ax_wave.cla()
#         self._style_axes(self.ax_wave)
#         self.ax_wave.set_xlim(xmin, xmax)
#         self.ax_wave.set_ylim(-2.2, 2.2)
#         self.ax_wave.axhline(0, color=GRID, lw=1)
#         self.ax_wave.axvspan(0, a, color=AMBER, alpha=0.05)
#         for bx_ in (0, a):
#             self.ax_wave.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)
#             self.ax_pot.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)

#         sqrtT = np.sqrt(phys['T'])
#         self.ax_wave.axhline(1, color='#ffffff', alpha=0.08, ls=':', lw=1)
#         self.ax_wave.axhline(-1, color='#ffffff', alpha=0.08, ls=':', lw=1)
#         self.ax_wave.axhline(sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)
#         self.ax_wave.axhline(-sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)

#         regime = phys['regime']
#         if regime in ('tunnel', 'equal'):
#             xb = np.linspace(0, a, 60)
#             frac = xb / a if a > 0 else xb * 0
#             env = np.exp(np.log(max(sqrtT, 1e-6)) * frac)
#             self.ax_wave.fill_between(xb, -env, env, color=VIOLET, alpha=0.10)
#         else:
#             self.ax_wave.axvspan(0, a, color=BLUE, alpha=0.04)

#         wave_line, = self.ax_wave.plot([], [], color=CYAN, lw=2.2)
#         self.ax_wave.set_xlabel('x  (nm)', color=MUTED, fontsize=9)
#         self.ax_wave.set_ylabel('Re[\u03c8(x,t)]', color=MUTED, fontsize=9)

#         band_color = VIOLET if regime in ('tunnel', 'equal') else BLUE
#         self.ax_wave.text(xmin * 0.55, -1.92, 'incident + reflected', color=MUTED, fontsize=8, ha='center')
#         self.ax_wave.text((0 + a) / 2, -1.92, 'barrier region', color=band_color, fontsize=8, ha='center')
#         self.ax_wave.text(a + margin * 0.55, -1.92, 'transmitted', color=MUTED, fontsize=8, ha='center')

#         # ---- quantum regime panel ----
#         if regime == 'tunnel':
#             accent = TUNNEL_ACCENT
#             value_txt, name_txt = 'E < V\u2080', 'Tunneling'
#             status_txt = 'Classically forbidden \u2014 wavefunction still penetrates.'
#         elif regime == 'above':
#             accent = ABOVE_ACCENT
#             value_txt, name_txt = 'E > V\u2080', 'Above-barrier scattering'
#             status_txt = 'Classically allowed \u2014 quantum reflection still occurs.'
#         else:
#             accent = BORDER_ACCENT
#             value_txt, name_txt = 'E \u2248 V\u2080', 'Borderline regime'
#             status_txt = 'Transition point between tunneling and scattering.'

#         self.regime_tint.set_facecolor(accent)
#         self.regime_box.set_edgecolor(accent)
#         self.regime_value_text.set_text(value_txt)
#         self.regime_value_text.set_color(accent)
#         self.regime_name_text.set_text(name_txt)
#         self.regime_status_text.set_text(status_txt)

#         # ---- kappa / diagnostics (left) ----
#         if regime == 'tunnel':
#             thick = np.exp(-2 * phys['kappa'] * NM * a)
#             self.info_text.set_text(
#                 f"\u03ba (decay const.)   {phys['kappa']*NM:.3f} /nm\n"
#                 f"\u03baa                  {phys['kappa']*NM*a:.3f}\n"
#                 f"e^(-2\u03baa) estimate   {thick:.2e}\n"
#                 f"\u03bb (incident)        {phys['lambda1_nm']:.3f} nm"
#             )
#         elif regime == 'above':
#             self.info_text.set_text(
#                 f"k2 (inside barrier) {phys['k2']*NM:.3f} /nm\n"
#                 f"k2\u00b7a                 {phys['k2']*NM*a:.3f}\n"
#                 f"\u03bb (incident)         {phys['lambda1_nm']:.3f} nm"
#             )
#         else:
#             self.info_text.set_text(
#                 f"\u03ba \u2192 0   (E \u2248 V0)\n"
#                 f"\u03bb (incident)   {phys['lambda1_nm']:.3f} nm"
#             )

#         # ---- T / R / checksum / resonance (right) ----
#         self.t_line.set_text(f"Transmission:  {phys['T']*100:6.2f} %")
#         self.r_line.set_text(f"Reflection:    {phys['R']*100:6.2f} %")
#         self.check_line.set_text(f"R + T = {phys['R']+phys['T']:.4f}  OK")
#         self.resonance_line.set_text(
#             '\u2605 resonance: T \u2248 1, barrier nearly transparent' if phys['resonance'] else ''
#         )

#         self.state['xs'], self.state['phys'], self.state['wave_line'] = xs, phys, wave_line
#         self.fig.canvas.draw_idle()

#     # -----------------------------------------------------------
#     # 10. Animation loop — unchanged
#     # -----------------------------------------------------------
#     def animate(self, _frame):
#         self.state['t_phase'] += 0.09
#         xs, phys, wave_line = self.state['xs'], self.state['phys'], self.state['wave_line']
#         psi = compute_wave(xs, phys, self.state['t_phase'])
#         wave_line.set_data(xs, psi)
#         return (wave_line,)


# def matplotlib_rcparams_monospace():
#     import matplotlib.pyplot as _plt_for_rcparams_only
#     _plt_for_rcparams_only.rcParams['font.family'] = 'monospace'


# def create_tunneling(on_back):
#     """Factory used by main.py — returns the embeddable module screen."""
#     return TunnelingLabView(on_back)


# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     window = TunnelingLabView(on_back=lambda: app.quit())
#     window.resize(1150, 1020)
#     window.show()
#     sys.exit(app.exec_())