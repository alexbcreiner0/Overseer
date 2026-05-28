from PyQt6 import (
    QtGui as qg,
    QtCore as qc,
    QtWidgets as qw
)

def recolor_icon(icon, size= 16):
    pixmap = icon.pixmap(size, size)
    image = pixmap.toImage()

    colors = {}
    for x in range(image.width()):
        for y in range(image.height()):
            c = qg.QColor(image.pixel(x,y))
            key = (c.red(), c.green(), c.blue(), c.alpha())
            colors[key] = colors.get(key, 0) + 1

    opaque_colors = [(rgba, count) for rgba, count in colors.items() if rgba[3] != 0]
    if not opaque_colors:
        return icon

    def brightness(rgba):
        r, g, b, _ = rgba
        return 0.299 * r + 0.587 * g + 0.114 * b

    opaque_colors.sort(key=lambda rc: brightness(rc[0]))  # darkest first
    fg_rgba, _ = opaque_colors[0]

    palette = qw.QApplication.palette()
    ink_color = palette.color(palette.ColorRole.WindowText)  # theme-aware "black"
    transparent = qg.QColor(0, 0, 0, 0)

    # 4. Remap pixels
    for x in range(image.width()):
        for y in range(image.height()):
            c = qg.QColor(image.pixel(x, y))
            rgba = (c.red(), c.green(), c.blue(), c.alpha())
            if rgba[3] == 0:
                # already transparent
                continue
            if rgba == fg_rgba:
                image.setPixelColor(x, y, transparent)
            else:
                image.setPixelColor(x, y, ink_color)

    return qg.QIcon(qg.QPixmap.fromImage(image))

# need PySide6
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import sys

class Example(QWidget):
    def __init__(self):
        super(Example, self).__init__()
        self.initUI()
        self.Button()

    def initUI(self):
        style = self.style()
        icon = style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton)
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(QIcon(icon))
        self.setWindowIcon(QIcon(icon))
        self.setGeometry(300, 300, 300, 300)

    def Button(self):
        Styles = list(QStyle.StandardPixmap)

        btn = [QToolButton(self) for i in range(len(Styles))]
        self.myHLayout = QGridLayout()
        j = 0
        k = 0
        style = self.style()
        for i in range(len(Styles)):
            btn[i].setText("%s" % (Styles[i].name))
            btn[i].setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            icon = style.standardIcon(Styles[i])
            btn[i].setIcon(QIcon(icon))
            self.myHLayout.addWidget(btn[i], j, k)

            if i == 0:
                k += 1
                pass
            elif 0 == i % 5:
                j += 1
                k = 0
            else:
                k += 1
        self.setLayout(self.myHLayout)

def main():
    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    app.exec()

if __name__ == '__main__':
    main()
