import sys
from PySide6 import QtCore, QtWidgets
import pyqtgraph.opengl as gl
from PySide6.QtGui import QColor

from model import BoxDimensions
from render import BoxItem


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Visualizer - Multiple Boxes")
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

        panel_layout.addRow("Width (X) Red", self.length_edit)
        panel_layout.addRow("Length (Y) Green", self.width_edit)
        panel_layout.addRow("Height (Z) Blue", self.height_edit)

        # --- Box management buttons ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.add_box_btn = QtWidgets.QPushButton("Add Box")
        self.add_box_btn.clicked.connect(self.on_add_box)
        btn_layout.addWidget(self.add_box_btn)
        
        self.update_btn = QtWidgets.QPushButton("Update Selected")
        self.update_btn.clicked.connect(self.on_update_box)
        btn_layout.addWidget(self.update_btn)
        
        self.delete_btn = QtWidgets.QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.on_delete_box)
        btn_layout.addWidget(self.delete_btn)
        
        panel_layout.addRow(btn_layout)

        # --- Box list ---
        self.box_list = QtWidgets.QListWidget()
        self.box_list.itemSelectionChanged.connect(self.on_box_selected)
        panel_layout.addRow("Boxes:", self.box_list)

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

        # --- Box management ---
        self.boxes = []  # List of BoxItem objects
        self.selected_box_index = None
        self.box_counter = 0
        
        # --- Add default box ---
        self.add_initial_box()

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

    def get_box_color(self, index):
        """Generate a unique color for each box"""
        colors = [
            (0.7, 0.45, 0.25, 0.8),   # brown
            (0.3, 0.6, 0.9, 0.8),     # blue
            (0.9, 0.4, 0.4, 0.8),     # red
            (0.4, 0.8, 0.4, 0.8),     # green
            (0.9, 0.7, 0.3, 0.8),     # gold
            (0.7, 0.3, 0.8, 0.8),     # purple
            (0.3, 0.8, 0.8, 0.8),     # cyan
            (0.9, 0.5, 0.2, 0.8),     # orange
        ]
        return colors[index % len(colors)]

    def get_color_name(self, index):
        """Get the color name for a box based on its index"""
        color_names = ["Brown", "Blue", "Red", "Green", "Gold", "Purple", "Cyan", "Orange"]
        return color_names[index % len(color_names)]

    def add_initial_box(self):
        """Add the initial default box"""
        dims = BoxDimensions(0.50, 0.30, 0.25)
        box = BoxItem(dims.length, dims.width, dims.height, pos=(0, 0, dims.height / 2.0))
        box.setColor(self.get_box_color(0))
        self.view.addItem(box)
        self.boxes.append(box)
        self.box_counter += 1
        color_name = self.get_color_name(0)
        self.box_list.addItem(f"Box {self.box_counter} ({color_name}): {dims.length}x{dims.width}x{dims.height}")
        self.box_list.setCurrentRow(0)
        self.selected_box_index = 0
        self.highlight_selected_box()

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

    def on_add_box(self):
        """Add a new box to the scene"""
        try:
            dims = self.parse_dims()
            # Offset position slightly so boxes don't overlap
            offset = len(self.boxes) * 0.3
            box = BoxItem(dims.length, dims.width, dims.height, 
                         pos=(offset, offset, dims.height / 2.0))
            box.setColor(self.get_box_color(len(self.boxes)))
            self.view.addItem(box)
            self.boxes.append(box)
            self.box_counter += 1
            
            color_name = self.get_color_name(len(self.boxes) - 1)
            self.box_list.addItem(f"Box {self.box_counter} ({color_name}): {dims.length}x{dims.width}x{dims.height}")
            self.box_list.setCurrentRow(len(self.boxes) - 1)
            self.selected_box_index = len(self.boxes) - 1
            self.highlight_selected_box()
            
            self.status.setText(f"Added Box {self.box_counter}: L={dims.length}, W={dims.width}, H={dims.height}")
        except Exception as e:
            self.status.setText(f"Error adding box: {e}")

    def on_update_box(self):
        """Update the selected box with new dimensions"""
        if self.selected_box_index is None:
            self.status.setText("No box selected")
            return
        
        try:
            dims = self.parse_dims()
            box = self.boxes[self.selected_box_index]
            box.pos[2] = dims.height / 2.0
            box.set_dimensions(dims.length, dims.width, dims.height)
            
            # Update list item text
            box_num = self.selected_box_index + 1
            color_name = self.get_color_name(self.selected_box_index)
            self.box_list.item(self.selected_box_index).setText(
                f"Box {box_num} ({color_name}): {dims.length}x{dims.width}x{dims.height}"
            )
            
            self.status.setText(f"Updated Box {box_num}: L={dims.length}, W={dims.width}, H={dims.height}")
        except Exception as e:
            self.status.setText(f"Error: {e}")

    def on_delete_box(self):
        """Delete the selected box"""
        if self.selected_box_index is None:
            self.status.setText("No box selected")
            return
        
        if len(self.boxes) <= 1:
            self.status.setText("Cannot delete the last box")
            return
        
        box = self.boxes[self.selected_box_index]
        self.view.removeItem(box)
        self.boxes.pop(self.selected_box_index)
        self.box_list.takeItem(self.selected_box_index)
        
        # Select a different box
        if self.selected_box_index >= len(self.boxes):
            self.selected_box_index = len(self.boxes) - 1
        self.box_list.setCurrentRow(self.selected_box_index)
        self.highlight_selected_box()
        
        self.status.setText(f"Deleted box")

    def on_box_selected(self):
        """Handle box selection from the list"""
        current_row = self.box_list.currentRow()
        if current_row >= 0:
            self.selected_box_index = current_row
            self.highlight_selected_box()

    def highlight_selected_box(self):
        """Visually highlight the selected box"""
        for i, box in enumerate(self.boxes):
            if i == self.selected_box_index:
                # Highlight selected box with bright yellow edges
                box.opts['edgeColor'] = (1.0, 1.0, 0.0, 1.0)  # bright yellow
                # box.opts['shader'] = 'shaded'
            else:
                # Normal black edges for other boxes
                box.opts['edgeColor'] = (0.0, 0.0, 0.0, 1.0)  # black
            box.update()

    def tick_move(self):
        """Move the selected box with WASDQE keys"""
        if self.selected_box_index is None:
            return
        
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
            self.boxes[self.selected_box_index].move_by(dx, dy, dz)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()