import sys

from PyQt5.QtWidgets import QApplication, QSizePolicy, QPushButton

from main import ModuleCard, MODULES


def test_module_cards_are_responsive_and_keep_explore_visible():
    app = QApplication.instance() or QApplication(sys.argv)
    card = ModuleCard(MODULES[0], lambda _: None)

    assert card.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert card.sizePolicy().verticalPolicy() == QSizePolicy.Preferred
    assert card.minimumHeight() >= 220
    assert card.findChild(QPushButton, "cardExplore") is not None
