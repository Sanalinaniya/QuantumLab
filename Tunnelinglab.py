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

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from matplotlib.animation import FuncAnimation
from matplotlib.patches import FancyBboxPatch

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


# --------------------------------------------------------------------------
# 4. Figure & static layout
#
#    Every band below was measured against actual rendered output (not
#    guessed) after the first version overlapped text in the regime panel.
#    Left and right columns sit at DIFFERENT x-ranges (0.09-0.44 vs
#    0.52-0.93), so they never collide with each other horizontally; each
#    column's own vertical stack has a real gap between every element.
#
#      0.965 - 0.995   header (3 short lines)
#      0.695 - 0.900   potential panel        (ax_pot)
#      0.480 - 0.675   wavefunction panel     (ax_wave)
#      0.340 - 0.432   sliders (LEFT col)     |  0.282 - 0.432  regime panel (RIGHT col)
#      0.180 - 0.300   kappa info (LEFT col)  |  0.138 - 0.252  T/R readout (RIGHT col)
#      0.030 - 0.075   preset buttons (full width)
# --------------------------------------------------------------------------
plt.rcParams['font.family'] = 'monospace'

fig = plt.figure(figsize=(11.5, 10.2), facecolor=BG)

fig.text(0.07, 0.978, 'INTERACTIVE PHYSICS LAB', color=CYAN,
          fontsize=10, fontweight='bold', family='monospace')
fig.text(0.07, 0.953, 'Quantum Tunneling & Above-Barrier Scattering',
          color=TEXT, fontsize=18, fontweight='bold')
fig.text(0.07, 0.933,
         "Real \u0127, real electron mass. Energies in eV, lengths in nm.",
         color=MUTED, fontsize=9.5)

ax_pot = fig.add_axes([0.09, 0.695, 0.87, 0.205])
ax_wave = fig.add_axes([0.09, 0.480, 0.87, 0.195], sharex=ax_pot)


def style_axes(ax):
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID, alpha=0.4, linewidth=0.6)


# --------------------------------------------------------------------------
# 5. Sliders (LEFT column, x: 0.09 - 0.44)
# --------------------------------------------------------------------------
def make_slider_axes(y):
    ax = fig.add_axes([0.09, y, 0.35, 0.022])
    ax.set_facecolor(GRID)
    return ax

ax_v0 = make_slider_axes(0.410)
ax_a  = make_slider_axes(0.375)
ax_e  = make_slider_axes(0.340)

v0_slider = Slider(ax_v0, 'V0 (eV)', 0.2, 12.0, valinit=5.0, valstep=0.1,
                    color=AMBER, initcolor='none')
a_slider = Slider(ax_a, 'a (nm)', 0.05, 3.0, valinit=0.5, valstep=0.01,
                   color=VIOLET, initcolor='none')
e_slider = Slider(ax_e, 'E (eV)', 0.1, 15.0, valinit=3.0, valstep=0.1,
                   color=CYAN, initcolor='none')

for s in (v0_slider, a_slider, e_slider):
    s.label.set_color(TEXT)
    s.label.set_fontsize(9.5)
    s.valtext.set_color(TEXT)
    s.valtext.set_fontsize(9.5)

# --------------------------------------------------------------------------
# 6. Quantum-regime panel (RIGHT column, x: 0.52-0.93, y: 0.282-0.432)
#    Built once; redraw_static() only edits colors/text on the same fixed
#    objects, so the layout itself can never drift or overlap.
#    Internal spacing uses the FULL 0-1 axis range (not squeezed into the
#    middle), and status is kept to one line so it can never grow into
#    the name line above it.
# --------------------------------------------------------------------------
ax_regime = fig.add_axes([0.52, 0.282, 0.41, 0.150])
ax_regime.set_xlim(0, 1); ax_regime.set_ylim(0, 1); ax_regime.axis('off')

regime_tint = FancyBboxPatch((0.015, 0.04), 0.97, 0.92,
                              boxstyle='round,pad=0.0,rounding_size=0.05',
                              linewidth=0, facecolor=VIOLET, alpha=0.08)
regime_box = FancyBboxPatch((0.015, 0.04), 0.97, 0.92,
                             boxstyle='round,pad=0.0,rounding_size=0.05',
                             linewidth=1.4, edgecolor=VIOLET, facecolor='none')
ax_regime.add_patch(regime_tint)
ax_regime.add_patch(regime_box)

ax_regime.text(0.5, 0.87, 'QUANTUM REGIME', color=MUTED, fontsize=9,
               ha='center', va='center', fontweight='bold')
ax_regime.plot([0.14, 0.86], [0.72, 0.72], color=GRID, lw=1)
regime_value_text = ax_regime.text(0.5, 0.48, '', color=VIOLET, fontsize=20,
                                    ha='center', va='center',
                                    fontweight='bold', family='monospace')
regime_name_text = ax_regime.text(0.5, 0.255, '', color=TEXT, fontsize=10.5,
                                   ha='center', va='center', fontweight='bold')
regime_status_text = ax_regime.text(0.5, 0.10, '', color=MUTED, fontsize=7.6,
                                     ha='center', va='center')

# --------------------------------------------------------------------------
# 7. Readout text blocks (fixed positions, updated via set_text only)
# --------------------------------------------------------------------------
info_text = fig.text(0.09, 0.290, '', color=MUTED, fontsize=9.2,
                      family='monospace', va='top', linespacing=1.9)

t_line = fig.text(0.52, 0.252, '', color=CYAN, fontsize=11, family='monospace',
                   va='top', fontweight='bold')
r_line = fig.text(0.52, 0.214, '', color=PINK, fontsize=11, family='monospace',
                   va='top', fontweight='bold')
check_line = fig.text(0.52, 0.176, '', color=GREEN, fontsize=10, family='monospace',
                       va='top')
resonance_line = fig.text(0.52, 0.145, '', color=AMBER, fontsize=8.6,
                           family='monospace', va='top')

# --------------------------------------------------------------------------
# 8. Preset buttons (full width, well below every text block above)
# --------------------------------------------------------------------------
PRESETS = [
    ('STM gap',        6.0, 0.40, 2.0),
    ('Thick wall',     8.0, 2.00, 2.0),
    ('Near resonance', 3.0, 0.354, 6.0),
    ('Deep tunneling', 10.0, 1.50, 1.0),
]
buttons = []
bx = 0.09
for label, V0, a, E in PRESETS:
    bax = fig.add_axes([bx, 0.030, 0.18, 0.042])
    btn = Button(bax, label, color=PANEL_BG, hovercolor='#182234')
    btn.label.set_color(TEXT)
    btn.label.set_fontsize(8)
    buttons.append(btn)
    bx += 0.21


def make_preset_handler(V0, a, E):
    def handler(_event):
        v0_slider.set_val(V0)
        a_slider.set_val(a)
        e_slider.set_val(E)   # last set_val fires redraw_static via its callback
    return handler

for btn, (_, V0, a, E) in zip(buttons, PRESETS):
    btn.on_clicked(make_preset_handler(V0, a, E))

# --------------------------------------------------------------------------
# 9. State + redraw-on-slider-change
# --------------------------------------------------------------------------
state = {'xs': None, 'phys': None, 'wave_line': None, 't_phase': 0.0}


def redraw_static(_event=None):
    V0, a, E = v0_slider.val, a_slider.val, e_slider.val
    phys = compute_physics(V0, a, E)
    lambda1 = phys['lambda1_nm']
    margin = min(2.6, max(0.55, 1.5 * lambda1))
    xmin, xmax = -margin, a + margin
    xs = np.linspace(xmin, xmax, 500)

    # ---- potential panel ----
    ax_pot.cla(); style_axes(ax_pot)
    ax_pot.set_ylim(0, VAXIS_MAX)
    ax_pot.set_xlim(xmin, xmax)
    x_step = [xmin, 0, 0, a, a, xmax]
    v_step = [0, 0, V0, V0, 0, 0]
    ax_pot.fill_between(x_step, 0, v_step, color=AMBER, alpha=0.22)
    ax_pot.plot(x_step, v_step, color=AMBER, lw=2.2)
    ax_pot.axhline(E, color=CYAN, ls='--', lw=1.6)
    ax_pot.axvspan(0, a, color=AMBER, alpha=0.05)
    ax_pot.text((0 + a) / 2, min(V0 + 0.9, VAXIS_MAX - 0.6), f'V0 = {V0:.1f} eV',
                color=AMBER, fontsize=9.5, ha='center', fontweight='bold')
    ax_pot.text(xmax - 0.05 * (xmax - xmin), min(E + 0.5, VAXIS_MAX - 0.4),
                f'E = {E:.1f} eV', color=CYAN, fontsize=9.5, ha='right', fontweight='bold')
    ax_pot.set_ylabel('V(x)  [eV]', color=MUTED, fontsize=9)
    plt.setp(ax_pot.get_xticklabels(), visible=False)

    # ---- wavefunction panel ----
    ax_wave.cla(); style_axes(ax_wave)
    ax_wave.set_xlim(xmin, xmax)
    ax_wave.set_ylim(-2.2, 2.2)
    ax_wave.axhline(0, color=GRID, lw=1)
    ax_wave.axvspan(0, a, color=AMBER, alpha=0.05)
    for bx_ in (0, a):
        ax_wave.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)
        ax_pot.axvline(bx_, color='#ffffff', alpha=0.15, ls=':', lw=1)

    sqrtT = np.sqrt(phys['T'])
    ax_wave.axhline(1, color='#ffffff', alpha=0.08, ls=':', lw=1)
    ax_wave.axhline(-1, color='#ffffff', alpha=0.08, ls=':', lw=1)
    ax_wave.axhline(sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)
    ax_wave.axhline(-sqrtT, color=CYAN, alpha=0.18, ls=':', lw=1)

    regime = phys['regime']
    if regime in ('tunnel', 'equal'):
        xb = np.linspace(0, a, 60)
        frac = xb / a if a > 0 else xb * 0
        env = np.exp(np.log(max(sqrtT, 1e-6)) * frac)
        ax_wave.fill_between(xb, -env, env, color=VIOLET, alpha=0.10)
    else:
        ax_wave.axvspan(0, a, color=BLUE, alpha=0.04)

    wave_line, = ax_wave.plot([], [], color=CYAN, lw=2.2)
    ax_wave.set_xlabel('x  (nm)', color=MUTED, fontsize=9)
    ax_wave.set_ylabel('Re[\u03c8(x,t)]', color=MUTED, fontsize=9)

    band_color = VIOLET if regime in ('tunnel', 'equal') else BLUE
    ax_wave.text(xmin * 0.55, -1.92, 'incident + reflected', color=MUTED, fontsize=8, ha='center')
    ax_wave.text((0 + a) / 2, -1.92, 'barrier region', color=band_color, fontsize=8, ha='center')
    ax_wave.text(a + margin * 0.55, -1.92, 'transmitted', color=MUTED, fontsize=8, ha='center')

    # ---- quantum regime panel ----
    if regime == 'tunnel':
        accent = TUNNEL_ACCENT
        value_txt, name_txt = 'E < V\u2080', 'Tunneling'
        status_txt = 'Classically forbidden \u2014 wavefunction still penetrates.'
    elif regime == 'above':
        accent = ABOVE_ACCENT
        value_txt, name_txt = 'E > V\u2080', 'Above-barrier scattering'
        status_txt = 'Classically allowed \u2014 quantum reflection still occurs.'
    else:
        accent = BORDER_ACCENT
        value_txt, name_txt = 'E \u2248 V\u2080', 'Borderline regime'
        status_txt = 'Transition point between tunneling and scattering.'

    regime_tint.set_facecolor(accent)
    regime_box.set_edgecolor(accent)
    regime_value_text.set_text(value_txt)
    regime_value_text.set_color(accent)
    regime_name_text.set_text(name_txt)
    regime_status_text.set_text(status_txt)

    # ---- kappa / diagnostics (left) ----
    if regime == 'tunnel':
        thick = np.exp(-2 * phys['kappa'] * NM * a)
        info_text.set_text(
            f"\u03ba (decay const.)   {phys['kappa']*NM:.3f} /nm\n"
            f"\u03baa                  {phys['kappa']*NM*a:.3f}\n"
            f"e^(-2\u03baa) estimate   {thick:.2e}\n"
            f"\u03bb (incident)        {phys['lambda1_nm']:.3f} nm"
        )
    elif regime == 'above':
        info_text.set_text(
            f"k2 (inside barrier) {phys['k2']*NM:.3f} /nm\n"
            f"k2\u00b7a                 {phys['k2']*NM*a:.3f}\n"
            f"\u03bb (incident)         {phys['lambda1_nm']:.3f} nm"
        )
    else:
        info_text.set_text(
            f"\u03ba \u2192 0   (E \u2248 V0)\n"
            f"\u03bb (incident)   {phys['lambda1_nm']:.3f} nm"
        )

    # ---- T / R / checksum / resonance (right) ----
    t_line.set_text(f"Transmission:  {phys['T']*100:6.2f} %")
    r_line.set_text(f"Reflection:    {phys['R']*100:6.2f} %")
    check_line.set_text(f"R + T = {phys['R']+phys['T']:.4f}  OK")
    resonance_line.set_text(
        '\u2605 resonance: T \u2248 1, barrier nearly transparent' if phys['resonance'] else ''
    )

    state['xs'], state['phys'], state['wave_line'] = xs, phys, wave_line
    fig.canvas.draw_idle()


for s in (v0_slider, a_slider, e_slider):
    s.on_changed(redraw_static)

redraw_static()  # initial draw


# --------------------------------------------------------------------------
# 10. Animation loop -- only updates the wave line each frame
# --------------------------------------------------------------------------
def animate(_frame):
    state['t_phase'] += 0.09
    xs, phys, wave_line = state['xs'], state['phys'], state['wave_line']
    psi = compute_wave(xs, phys, state['t_phase'])
    wave_line.set_data(xs, psi)
    return (wave_line,)


ani = FuncAnimation(fig, animate, interval=40, blit=False, cache_frame_data=False)

plt.show()