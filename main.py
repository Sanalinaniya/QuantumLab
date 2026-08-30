"""
QuantumLab — main application shell.

This is the single entry point. It owns:
  - the home screen (four module cards)
  - navigation between the home screen and each module
  - the About panel

Each module (modules/particle_box.py, harmonic_oscillator.py,
wave_packet.py, tunneling.py) exposes a factory function of the shape
    create_XXX(on_back) -> QWidget
which builds that module's whole screen and wires its "← Back to
QuantumLab" button to call `on_back` — a callback this file provides.
Modules are built fresh each time you open them (not kept alive in the
background), so switching modules can't leave a stray animation timer
running against a screen you've already left.

Run:
    pip install numpy matplotlib PyQt5
    python main.py
"""

import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QStackedWidget, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QBrush, QPainterPath

from quantum_visualizer import QuantumVisualizer
from harmonic_oscillator import HarmonicOscillatorView
from quantum_wave_packet import WavePacketView
from Tunnelinglab import create_tunneling as build_tunneling


def _wrap_module_screen(title, body_widget, on_back):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(12)

    top_row = QHBoxLayout()
    back_btn = QPushButton("← Back to QuantumLab")
    back_btn.setObjectName("backButton")
    back_btn.clicked.connect(on_back)
    top_row.addWidget(back_btn)
    top_row.addStretch()
    layout.addLayout(top_row)

    label = QLabel(title)
    label.setStyleSheet("font-size: 24px; font-weight: 700; color: #1e293b;")
    layout.addWidget(label)

    body_widget.setParent(container)
    layout.addWidget(body_widget)
    layout.addStretch()
    return container


def create_particle_box(on_back):
    return _wrap_module_screen("Particle in a Box", QuantumVisualizer(), on_back)


def create_harmonic_oscillator(on_back):
    return _wrap_module_screen("Harmonic Oscillator", HarmonicOscillatorView(), on_back)


def create_wave_packet(on_back):
    return _wrap_module_screen("Wave Packet", WavePacketView(), on_back)


def create_tunneling(on_back):
    return _wrap_module_screen("Quantum Tunneling", build_tunneling(on_back), on_back)


ACCENT = "#5fd98a"
ACCENT_ALT = "#f5b642"

MODULES = [
    {
        "key": "particle_box",
        "title": "Particle in a Box",
        "icon": "⚛",
        "blurb": "Quantum states, wavefunctions, probability density, "
                 "energy levels, adjustable box length, state comparison.",
        "factory": create_particle_box,
    },
    {
        "key": "harmonic_oscillator",
        "title": "Harmonic Oscillator",
        "icon": "∿",
        "blurb": "Energy levels, wavefunctions riding their levels, "
                 "nodes, parity, turning points, expectation values.",
        "factory": create_harmonic_oscillator,
    },
    {
        "key": "wave_packet",
        "title": "Wave Packet",
        "icon": "≋",
        "blurb": "A localized Gaussian packet evolving in time — watch "
                 "quantum motion and the uncertainty principle directly.",
        "factory": create_wave_packet,
    },
    {
        "key": "tunneling",
        "title": "Quantum Tunneling",
        "icon": "▰",
        "blurb": "A wave packet meets a potential barrier — literal "
                 "motion, splitting into reflected and transmitted parts.",
        "factory": create_tunneling,
    },
]


def _shell_stylesheet():
    return f"""
        QWidget {{ font-size: 15px; background-color: #080b11; color: #e7edf5; }}
        QLabel {{ color: #e7edf5; font-size: 15px; }}
        QPushButton {{
            font-weight: 700; font-size: 15px; padding: 8px 20px; border-radius: 10px;
            border: 1px solid {ACCENT}; color: #e7edf5; background: #0b1119;
        }}
        QPushButton:hover {{ background: #15232a; }}
        QPushButton:pressed {{ background: #111827; }}
        QPushButton#backButton {{ font-size: 13px; padding: 6px 14px; font-weight: 600; }}
        QPushButton#cardExplore {{
            font-size: 14px; padding: 9px 0px; border-radius: 9px;
            border: none; color: #080b11; background: {ACCENT_ALT};
        }}
        QPushButton#cardExplore:hover {{ background: #ffd07d; }}
        QFrame#card {{
            background: #0b1119; border: 1px solid #1e2a3a; border-radius: 16px;
        }}
    """


class ModuleCard(QFrame):
    """One clickable card on the home screen for a single module."""

    def __init__(self, module_info, on_open):
        super().__init__()
        self.setObjectName("card")
        self.setFixedSize(300, 210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        icon_label = QLabel(module_info["icon"])
        icon_font = QFont()
        icon_font.setPointSize(26)
        icon_label.setFont(icon_font)
        icon_label.setStyleSheet(f"color: {ACCENT};")
        icon_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(module_info["title"])
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #e7edf5;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)

        blurb_label = QLabel(module_info["blurb"])
        blurb_label.setWordWrap(True)
        blurb_label.setStyleSheet("color: #7c8aa0; font-size: 12px; font-weight: 500;")
        blurb_label.setAlignment(Qt.AlignCenter)

        explore_btn = QPushButton("EXPLORE")
        explore_btn.setObjectName("cardExplore")
        explore_btn.clicked.connect(lambda: on_open(module_info))

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(blurb_label, stretch=1)
        layout.addWidget(explore_btn)


class QuantumBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.particles = []
        self.wave_phase = 0.0
        for _ in range(18):
            self.particles.append({
                "x": 0.08 + 0.84 * (0.1 + 0.8 * (_ % 6) / 6),
                "y": 0.12 + 0.72 * ((_ % 3) / 3),
                "vx": (0.12 + (_ % 5) * 0.04) * (1 if _ % 2 == 0 else -1),
                "vy": (0.08 + (_ % 4) * 0.03) * (1 if _ % 3 == 0 else -1),
                "r": 2.2 + (_ % 5) * 0.8,
                "c": QColor(95 + (_ % 4) * 25, 217, 138, 120) if _ % 2 == 0 else QColor(245, 182, 66, 110),
            })
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)

    def _animate(self):
        self.wave_phase += 0.06
        for p in self.particles:
            p["x"] += p["vx"] * 0.006
            p["y"] += p["vy"] * 0.006
            if p["x"] < 0.02 or p["x"] > 0.98:
                p["vx"] *= -1
            if p["y"] < 0.08 or p["y"] > 0.92:
                p["vy"] *= -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # faint warm glow behind content
        glow = QColor(95, 217, 138, 40)
        painter.setPen(QPen(glow, 1, Qt.SolidLine))
        painter.setBrush(QBrush(QColor(95, 217, 138, 18)))
        painter.drawEllipse(int(w * 0.22), int(h * 0.23), int(w * 0.3), int(h * 0.3))

        painter.setPen(QPen(QColor(245, 182, 66, 50), 1))
        for i in range(4):
            y = h * (0.16 + i * 0.18)
            amp = 18 + i * 8
            painter.drawPath(self._wave_path(w, y, amp, i))

        # transparent cat in a box
        box_x, box_y, box_w, box_h = w * 0.68, h * 0.52, w * 0.18, h * 0.18
        painter.setPen(QPen(QColor(95, 217, 138, 50), 2))
        painter.setBrush(QBrush(QColor(95, 217, 138, 12)))
        painter.drawRect(int(box_x), int(box_y), int(box_w), int(box_h))
        painter.setPen(QPen(QColor(95, 217, 138, 70), 2))
        painter.drawLine(int(box_x + box_w * 0.18), int(box_y + box_h * 0.7), int(box_x + box_w * 0.18), int(box_y + box_h * 0.2))
        painter.drawLine(int(box_x + box_w * 0.82), int(box_y + box_h * 0.7), int(box_x + box_w * 0.82), int(box_y + box_h * 0.2))
        painter.drawEllipse(int(box_x + box_w * 0.47), int(box_y + box_h * 0.24), int(box_w * 0.14), int(box_h * 0.1))
        painter.drawLine(int(box_x + box_w * 0.36), int(box_y + box_h * 0.44), int(box_x + box_w * 0.32), int(box_y + box_h * 0.58))
        painter.drawLine(int(box_x + box_w * 0.64), int(box_y + box_h * 0.44), int(box_x + box_w * 0.68), int(box_y + box_h * 0.58))
        painter.drawArc(int(box_x + box_w * 0.38), int(box_y + box_h * 0.46), int(box_w * 0.24), int(box_h * 0.18), 0, 180 * 16)

        # floating particles
        for p in self.particles:
            x = int(p["x"] * w)
            y = int(p["y"] * h)
            r = int(p["r"])
            painter.setPen(QPen(p["c"], 1))
            painter.setBrush(QBrush(p["c"]))
            painter.drawEllipse(x, y, r * 2, r * 2)

    def _wave_path(self, w, y, amp, phase_index):
        path = QPainterPath()
        start_x = 0
        path.moveTo(0, y)
        for x in range(0, w + 1, 12):
            wx = x / w
            offset = amp * (0.5 + 0.5 * __import__('math').sin(wx * 22 + self.wave_phase + phase_index))
            path.lineTo(x, y + offset)
        return path


class HomeScreen(QWidget):
    def __init__(self, on_open_module, on_open_about):
        super().__init__()

        self.background = QuantumBackground(self)
        self.background.lower()
        self.background.resize(self.size())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 30)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("⚛  QUANTUMLAB")
        title_font = QFont()
        title_font.setPointSize(42)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {ACCENT};")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Interactive Quantum Mechanics Lab")
        subtitle_font = QFont()
        subtitle_font.setPointSize(18)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #dfe7f3; font-weight: 600;")
        subtitle.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Explore  •  Visualize  •  Experiment  •  Understand")
        tagline.setStyleSheet("color: #7c8aa0; font-weight: 600; font-size: 13px;")
        tagline.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(tagline)

        grid = QGridLayout()
        grid.setSpacing(22)
        grid.setAlignment(Qt.AlignCenter)
        for i, module_info in enumerate(MODULES):
            card = ModuleCard(module_info, on_open_module)
            grid.addWidget(card, i // 2, i % 2)

        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)
        grid_row = QHBoxLayout()
        grid_row.addStretch()
        grid_row.addWidget(grid_wrap)
        grid_row.addStretch()
        layout.addLayout(grid_row)

        layout.addStretch()

        about_btn = QPushButton("About QuantumLab")
        about_btn.clicked.connect(on_open_about)
        about_row = QHBoxLayout()
        about_row.addStretch()
        about_row.addWidget(about_btn)
        about_row.addStretch()
        layout.addLayout(about_row)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "background"):
            self.background.resize(self.size())


class AboutBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.particles = []
        self.wave_phase = 0.0
        for i in range(20):
            self.particles.append({
                "x": 0.08 + 0.84 * (i % 5) / 5,
                "y": 0.16 + 0.68 * (i % 4) / 4,
                "vx": (0.08 + (i % 6) * 0.02) * (1 if i % 2 == 0 else -1),
                "vy": (0.05 + (i % 5) * 0.02) * (1 if i % 3 == 0 else -1),
                "r": 2.0 + (i % 5) * 0.7,
                "c": QColor(95, 217, 138, 90) if i % 2 == 0 else QColor(245, 182, 66, 85),
            })
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(35)

    def _animate(self):
        self.wave_phase += 0.05
        for p in self.particles:
            p["x"] += p["vx"] * 0.006
            p["y"] += p["vy"] * 0.006
            if p["x"] < 0.02 or p["x"] > 0.98:
                p["vx"] *= -1
            if p["y"] < 0.08 or p["y"] > 0.92:
                p["vy"] *= -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.setPen(QPen(QColor(95, 217, 138, 28), 1))
        for i in range(6):
            y = h * (0.18 + i * 0.12)
            path = QPainterPath()
            path.moveTo(0, y)
            for x in range(0, w + 1, 14):
                wx = x / max(1, w)
                offset = 18 + i * 10
                oy = offset * (0.5 + 0.5 * __import__('math').sin(wx * 18 + self.wave_phase + i))
                path.lineTo(x, y + oy)
            painter.drawPath(path)

        box_x, box_y, box_w, box_h = w * 0.58, h * 0.62, w * 0.18, h * 0.18
        painter.setPen(QPen(QColor(95, 217, 138, 60), 2))
        painter.setBrush(QBrush(QColor(95, 217, 138, 10)))
        painter.drawRect(int(box_x), int(box_y), int(box_w), int(box_h))
        painter.setPen(QPen(QColor(95, 217, 138, 75), 2))
        painter.drawEllipse(int(box_x + box_w * 0.46), int(box_y + box_h * 0.22), int(box_w * 0.12), int(box_h * 0.1))
        painter.drawLine(int(box_x + box_w * 0.36), int(box_y + box_h * 0.42), int(box_x + box_w * 0.3), int(box_y + box_h * 0.56))
        painter.drawLine(int(box_x + box_w * 0.64), int(box_y + box_h * 0.42), int(box_x + box_w * 0.7), int(box_y + box_h * 0.56))
        painter.drawArc(int(box_x + box_w * 0.38), int(box_y + box_h * 0.45), int(box_w * 0.24), int(box_h * 0.18), 0, 180 * 16)

        for p in self.particles:
            x = int(p["x"] * w)
            y = int(p["y"] * h)
            r = int(p["r"])
            painter.setPen(QPen(p["c"], 1))
            painter.setBrush(QBrush(p["c"]))
            painter.drawEllipse(x, y, r * 2, r * 2)


class AboutScreen(QWidget):
    def __init__(self, on_back):
        super().__init__()
        self.background = AboutBackground(self)
        self.background.lower()
        self.background.resize(self.size())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        back_btn = QPushButton("← Back to QuantumLab")
        back_btn.setObjectName("backButton")
        back_btn.clicked.connect(on_back)
        back_row = QHBoxLayout()
        back_row.addWidget(back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)

        title = QLabel("⚛  QuantumLab")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {ACCENT};")
        layout.addWidget(title)

        description = QLabel(
            "An interactive visualization toolkit for exploring fundamental "
            "concepts in quantum mechanics — built to make the mathematics "
            "of quantum systems tangible rather than abstract."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #dfe7f3; font-size: 15px; font-weight: 500;")
        layout.addWidget(description)

        modules_title = QLabel("Modules")
        modules_title_font = QFont()
        modules_title_font.setPointSize(16)
        modules_title_font.setBold(True)
        modules_title.setFont(modules_title_font)
        modules_title.setStyleSheet(f"color: {ACCENT}; margin-top: 12px;")
        layout.addWidget(modules_title)

        for module_info in MODULES:
            line = QLabel(f"{module_info['icon']}  {module_info['title']} — {module_info['blurb']}")
            line.setWordWrap(True)
            line.setStyleSheet("color: #dfe7f3; font-size: 14px; font-weight: 500;")
            layout.addWidget(line)

        layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "background"):
            self.background.resize(self.size())


class QuantumLabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuantumLab — Interactive Quantum Mechanics Lab")
        self.resize(1300, 820)
        self.setStyleSheet(_shell_stylesheet())

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_screen = HomeScreen(self._open_module, self._open_about)
        self.stack.addWidget(self.home_screen)
        self.stack.setCurrentWidget(self.home_screen)

        # Module/About screens are built fresh each time they're opened
        # (see module docstring) rather than kept around, so we only
        # ever hold a reference to whichever one is currently showing.
        self._current_secondary_widget = None

    def _open_module(self, module_info):
        widget = module_info["factory"](self._go_home)
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        self._current_secondary_widget = widget

    def _open_about(self):
        about = AboutScreen(self._go_home)
        self.stack.addWidget(about)
        self.stack.setCurrentWidget(about)
        self._current_secondary_widget = about

    def _go_home(self):
        self.stack.setCurrentWidget(self.home_screen)
        # Clean up the screen we just left so it isn't kept alive in
        # memory (and so any timer it owns is fully released, not just
        # paused) once we've navigated away from it.
        if self._current_secondary_widget is not None:
            self.stack.removeWidget(self._current_secondary_widget)
            self._current_secondary_widget.deleteLater()
            self._current_secondary_widget = None


def main():
    app = QApplication(sys.argv)
    window = QuantumLabWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
