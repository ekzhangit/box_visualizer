import sys
from PySide6 import QtCore, QtWidgets
import pyqtgraph.opengl as gl
from PySide6.QtGui import QColor

from model import BoxDimensions
from render import BoxItem


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Visualizer (Milestone 1)")
        self.resize(1100, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        panel = QtWidgets.QFrame()
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        panel_layout = QtWidgets.QFormLayout(panel)

        self.length_edit = QtWidgets.QLineEdit("0.50")
        self.width_edit = QtWidgets.QLineEdit("0.30")
        self.height_edit = QtWidgets.QLineEdit("0.25")

        panel_layout.addRow("Length (X)", self.length_edit)
        panel_layout.addRow("Width (Y)", self.width_edit)
        panel_layout.addRow("Height (Z)", self.height_edit)

        self.update_btn = QtWidgets.QPushButton("Update Box")
        self.update_btn.clicked.connect(self.on_update_box)
        panel_layout.addRow(self.update_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        panel_layout.addRow("Status", self.status)

        # --- 3D view ---
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=2.0, elevation=20, azimuth=45)
        self.view.setBackgroundColor('w')  # white background

        # --- Grid (dark enough to see) ---
        grid = gl.GLGridItem()
        grid.setSize(4, 4)
        grid.setSpacing(0.5, 0.5)
        grid.setColor(QColor(80, 80, 80, 255))  # dark grey (R, G, B, Opacity)
        grid.translate(0, 0, -0.001)  # avoid z-fighting with the box
        self.view.addItem(grid)

        # --- Thick axes ---
        self.add_thick_axes(length=1.0, width=4.0)

        # --- Default box ---
        dims = BoxDimensions(0.50, 0.30, 0.25)
        self.box = BoxItem(dims.length, dims.width, dims.height, pos=(0, 0, dims.height / 2.0))
        self.view.addItem(self.box)

        layout.addWidget(panel, 0)
        layout.addWidget(self.view, 1)

        # --- Movement ---
        self.held = set()
        self.move_timer = QtCore.QTimer(self)
        self.move_timer.timeout.connect(self.tick_move)
        self.move_timer.start(16)

        # --- Keyboard focus + global key capture ---
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.setFocus()
        QtWidgets.QApplication.instance().installEventFilter(self)

    def add_thick_axes(self, length=1.0, width=3.0):
        # X axis (red)
        x = gl.GLLinePlotItem(
            pos=[[0, 0, 0], [length, 0, 0]],
            color=(1, 0, 0, 1),
            width=width,
            antialias=True
        )
        # Y axis (green)
        y = gl.GLLinePlotItem(
            pos=[[0, 0, 0], [0, length, 0]],
            color=(0, 0.6, 0, 1),
            width=width,
            antialias=True
        )
        # Z axis (blue)
        z = gl.GLLinePlotItem(
            pos=[[0, 0, 0], [0, 0, length]],
            color=(0, 0, 1, 1),
            width=width,
            antialias=True
        )

        self.view.addItem(x)
        self.view.addItem(y)
        self.view.addItem(z)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            self.held.add(event.key())
            return False
        if event.type() == QtCore.QEvent.KeyRelease:
            self.held.discard(event.key())
            return False
        return super().eventFilter(obj, event)

    def parse_dims(self) -> BoxDimensions:
        L = float(self.length_edit.text())
        W = float(self.width_edit.text())
        H = float(self.height_edit.text())
        dims = BoxDimensions(L, W, H)
        dims.validate()
        return dims

    def on_update_box(self):
        try:
            dims = self.parse_dims()
            self.box.pos[2] = dims.height / 2.0
            self.box.set_dimensions(dims.length, dims.width, dims.height)
            self.status.setText(f"Updated: L={dims.length}, W={dims.width}, H={dims.height}")
        except Exception as e:
            self.status.setText(f"Error: {e}")

    def tick_move(self):
        speed = 0.6
        dt = 0.016

        dx = dy = dz = 0.0
        if QtCore.Qt.Key_W in self.held: dy += speed * dt
        if QtCore.Qt.Key_S in self.held: dy -= speed * dt
        if QtCore.Qt.Key_D in self.held: dx += speed * dt
        if QtCore.Qt.Key_A in self.held: dx -= speed * dt
        if QtCore.Qt.Key_E in self.held: dz += speed * dt
        if QtCore.Qt.Key_Q in self.held: dz -= speed * dt

        if dx or dy or dz:
            self.box.move_by(dx, dy, dz)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
