import sys
import os
import json
import re

from PySide6 import QtCore, QtWidgets
import pyqtgraph.opengl as gl
from PySide6.QtGui import QColor

from model import BoxDimensions
from render import BoxItem

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Visualizer - LiDAR Integration")
        self.resize(1100, 700)

        # --- LiDAR Configuration ---
        self.base_dir = r"C:\Senior Design\LiDAR-Volume-Measure"

        self.lidar_exe_path = os.environ.get(
            "LIDAR_EXE",
            os.path.join(self.base_dir, r"build\Release\len_wid_addHeight.exe")
        )

        self.launch_file_path = os.path.join(
            self.base_dir, r"sick_scan_xd\launch\sick_tim_5xx.launch"
        )

        self.lidar_default_args = [
            self.launch_file_path,
            "hostname:=169.254.14.157"
        ]

        # --- UI Setup ---
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        panel = QtWidgets.QFrame()
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        panel_layout = QtWidgets.QFormLayout(panel)

        self.length_edit = QtWidgets.QLineEdit("0.50")
        self.width_edit  = QtWidgets.QLineEdit("0.30")
        self.height_edit = QtWidgets.QLineEdit("0.25")

        panel_layout.addRow("Width (X) Red",    self.length_edit)
        panel_layout.addRow("Length (Y) Green",  self.width_edit)
        panel_layout.addRow("Height (Z) Blue",   self.height_edit)

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

        self.scan_btn = QtWidgets.QPushButton("Scan Box")
        self.scan_btn.clicked.connect(self.on_scan_box)
        btn_layout.addWidget(self.scan_btn)

        panel_layout.addRow(btn_layout)

        self.box_list = QtWidgets.QListWidget()
        self.box_list.itemSelectionChanged.connect(self.on_box_selected)
        panel_layout.addRow("Boxes:", self.box_list)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setWordWrap(True)
        panel_layout.addRow("Status", self.status)

        # --- 3D view ---
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=2.0, elevation=20, azimuth=45)
        self.view.setBackgroundColor('w')

        # --- Floor grid: lies flat, corner at origin, extends +X and +Y ---
        bottom_grid = gl.GLGridItem()
        bottom_grid.setSize(2, 2)
        bottom_grid.setSpacing(0.5, 0.5)
        bottom_grid.setColor(QColor(80, 80, 80, 255))
        bottom_grid.translate(1, 1, 0)          # shift so corner sits at origin
        self.view.addItem(bottom_grid)

        # --- Back wall (XZ plane at Y=0): rotate 90° around X, then shift centre up and right ---
        xz_grid_wall = gl.GLGridItem()
        xz_grid_wall.setSize(2, 2)
        xz_grid_wall.setSpacing(0.5, 0.5)
        xz_grid_wall.setColor(QColor(80, 80, 80, 255))
        xz_grid_wall.rotate(90, 1, 0, 0)               # tip XY plane → XZ plane
        xz_grid_wall.translate(1, 0, 1)            # centre of 3×3 panel lands at (1.5, 0, 1.5)
        self.view.addItem(xz_grid_wall)

        # --- Side wall (YZ plane at X=0): rotate 90° around Y, then shift centre up and back ---
        yz_grid_wall = gl.GLGridItem()
        yz_grid_wall.setSize(2, 2)
        yz_grid_wall.setSpacing(1, 1)
        yz_grid_wall.setColor(QColor(80, 80, 80, 255))
        yz_grid_wall.rotate(90, 0, 1, 0)               # tip XY plane → YZ plane
        yz_grid_wall.translate(0, 1, 1)            # centre of 3×3 panel lands at (0, 1.5, 1.5)
        self.view.addItem(yz_grid_wall)

        self.add_thick_axes(length=1.0, width=4.0)

        # --- Box management ---
        self.boxes = []
        self.selected_box_index = None
        self.box_counter = 0
        self.add_initial_box()

        layout.addWidget(panel, 0)
        layout.addWidget(self.view, 1)

        # --- Movement Timer ---
        self.held = set()
        self.move_timer = QtCore.QTimer(self)
        self.move_timer.timeout.connect(self.tick_move)
        self.move_timer.start(16)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        QtWidgets.QApplication.instance().installEventFilter(self)

        # --- LiDAR scan process ---
        self.scan_proc = QtCore.QProcess(self)
        self.scan_proc.readyReadStandardOutput.connect(self._scan_read_stdout)
        self.scan_proc.readyReadStandardError.connect(self._scan_read_stderr)
        self.scan_proc.finished.connect(self._scan_finished)

        self._scan_stdout_buf = ""
        self._scan_stderr_buf = ""
        # Tracks whether we have already sent the second \n (scan 2 trigger)
        self._scan_sent_second = False

    # ------------------------------------------------------------------
    # 3D helpers
    # ------------------------------------------------------------------

    def add_thick_axes(self, length=1.0, width=3.0):
        for pos, color in [
            ([[0,0,0],[length,0,0]], (1,0,0,1)),
            ([[0,0,0],[0,length,0]], (0,0.6,0,1)),
            ([[0,0,0],[0,0,length]], (0,0,1,1))
        ]:
            axis = gl.GLLinePlotItem(pos=pos, color=color, width=width, antialias=True)
            self.view.addItem(axis)

    def get_box_color(self, index):
        colors = [(0.7,0.45,0.25,0.8),(0.3,0.6,0.9,0.8),(0.9,0.4,0.4,0.8),(0.4,0.8,0.4,0.8)]
        return colors[index % len(colors)]

    def get_color_name(self, index):
        names = ["Brown","Blue","Red","Green","Gold","Purple","Cyan","Orange"]
        return names[index % len(names)]

    def add_initial_box(self):
        dims = BoxDimensions(0.50, 0.30, 0.25)
        box = BoxItem(dims.length, dims.width, dims.height, pos=(0.2, 0.2, dims.height / 2.0))
        box.setColor(self.get_box_color(0))
        self.view.addItem(box)
        self.boxes.append(box)
        self.box_counter += 1
        self.box_list.addItem(f"Box {self.box_counter} ({self.get_color_name(0)}): 0.5x0.3x0.25")
        self.box_list.setCurrentRow(0)
        self.selected_box_index = 0
        self.highlight_selected_box()

    # ------------------------------------------------------------------
    # Event filter for keyboard movement
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            self.held.add(event.key())
        elif event.type() == QtCore.QEvent.KeyRelease:
            self.held.discard(event.key())
        return super().eventFilter(obj, event)

    def parse_dims(self) -> BoxDimensions:
        dims = BoxDimensions(
            float(self.length_edit.text()),
            float(self.width_edit.text()),
            float(self.height_edit.text())
        )
        dims.validate()
        return dims

    # ------------------------------------------------------------------
    # Box CRUD
    # ------------------------------------------------------------------

    def on_add_box(self):
        try:
            dims = self.parse_dims()
            offset = len(self.boxes) * 0.3
            box = BoxItem(dims.length, dims.width, dims.height, pos=(offset, offset, dims.height / 2.0))
            box.setColor(self.get_box_color(len(self.boxes)))
            self.view.addItem(box)
            self.boxes.append(box)
            self.box_counter += 1
            self.box_list.addItem(
                f"Box {self.box_counter} ({self.get_color_name(len(self.boxes)-1)}): "
                f"{dims.length}x{dims.width}x{dims.height}"
            )
            self.box_list.setCurrentRow(len(self.boxes) - 1)
            self.status.setText(f"Added Box {self.box_counter}")
        except Exception as e:
            self.status.setText(f"Error adding box: {e}")

    def on_update_box(self):
        if self.selected_box_index is None:
            return
        try:
            dims = self.parse_dims()
            box = self.boxes[self.selected_box_index]
            box.pos[2] = dims.height / 2.0
            box.set_dimensions(dims.length, dims.width, dims.height)
            self.box_list.item(self.selected_box_index).setText(
                f"Box {self.selected_box_index+1} ({self.get_color_name(self.selected_box_index)}): "
                f"{dims.length}x{dims.width}x{dims.height}"
            )
            self.status.setText("Updated Selected Box")
        except Exception as e:
            self.status.setText(f"Error: {e}")

    def on_delete_box(self):
        if self.selected_box_index is not None and len(self.boxes) > 1:
            self.view.removeItem(self.boxes.pop(self.selected_box_index))
            self.box_list.takeItem(self.selected_box_index)
            self.selected_box_index = self.box_list.currentRow()
            self.highlight_selected_box()

    def on_box_selected(self):
        self.selected_box_index = self.box_list.currentRow()
        self.highlight_selected_box()

    def highlight_selected_box(self):
        for i, box in enumerate(self.boxes):
            box.opts['edgeColor'] = (1,1,0,1) if i == self.selected_box_index else (0,0,0,1)
            box.update()

    def tick_move(self):
        if self.selected_box_index is None:
            return
        speed, dt = 0.6, 0.016
        dx = dy = dz = 0.0
        if QtCore.Qt.Key_W in self.held: dy += speed * dt
        if QtCore.Qt.Key_S in self.held: dy -= speed * dt
        if QtCore.Qt.Key_D in self.held: dx += speed * dt
        if QtCore.Qt.Key_A in self.held: dx -= speed * dt
        if QtCore.Qt.Key_E in self.held: dz += speed * dt
        if QtCore.Qt.Key_Q in self.held: dz -= speed * dt
        if dx or dy or dz:
            self.boxes[self.selected_box_index].move_by(dx, dy, dz)

    # ------------------------------------------------------------------
    # LiDAR scan — two-step interactive flow
    # ------------------------------------------------------------------

    def on_scan_box(self):
        """Start len_wid_addHeight.exe. The C program waits for two Enter
        presses (one per scan). We send them via QProcess stdin, showing a
        dialog between scans so the user can rotate the box."""

        if self.scan_proc.state() != QtCore.QProcess.NotRunning:
            return

        exe = self.lidar_exe_path
        if not os.path.exists(exe):
            self.status.setText(f"EXE NOT FOUND:\n{exe}")
            return

        if not os.path.exists(self.launch_file_path):
            self.status.setText(f"LAUNCH FILE NOT FOUND:\n{self.launch_file_path}")
            return

        exe_dir = os.path.dirname(exe)

        # Inject exe_dir into PATH so the process finds sick_scan_xd_shared_lib.dll,
        # but set the working directory to base_dir — this matches running manually from
        # C:\Senior Design\LiDAR-Volume-Measure, which sick_scan_xd requires to resolve
        # its internal config/launch paths correctly.
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PATH", exe_dir + os.pathsep + env.value("PATH"))

        self._scan_stdout_buf = ""
        self._scan_stderr_buf = ""
        self._scan_sent_second = False   # reset two-step flag

        self.scan_btn.setEnabled(False)
        self.status.setText("Connecting to LiDAR...")

        self.scan_proc.setProcessEnvironment(env)
        self.scan_proc.setProgram(exe)
        self.scan_proc.setArguments(self.lidar_default_args)
        self.scan_proc.setWorkingDirectory(self.base_dir)  # ← must match manual run dir
        self.scan_proc.start()

        if not self.scan_proc.waitForStarted(3000):
            self.scan_btn.setEnabled(True)
            self.status.setText(f"Process Error: {self.scan_proc.errorString()}")
            return

        # Send first newline → triggers getchar() for Measurement 1 in the C program.
        # The C program prints MEASUREMENT_PROMPT:1 before its getchar(), so it is
        # already waiting by the time we write. If it hasn't flushed yet the OS
        # will buffer the \n until getchar() is called.
        self.scan_proc.write(b'\n')
        self.status.setText("Scan 1/2 — measuring Width + Depth…")

    def _scan_read_stdout(self):
        """Accumulate stdout. When the C program signals it is ready for scan 2
        (MEASUREMENT_PROMPT:2) show a dialog so the user can rotate the box,
        then send the second newline."""

        data = bytes(self.scan_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._scan_stdout_buf += data

        # Detect the sentinel the C program emits before its second getchar()
        if not self._scan_sent_second and "MEASUREMENT_PROMPT:2" in self._scan_stdout_buf:
            self._scan_sent_second = True
            self.status.setText("Scan 1/2 complete — waiting for box rotation…")

            # Block the event loop briefly with a dialog; the C process is also
            # blocked on getchar() so there is no race condition.
            QtWidgets.QMessageBox.information(
                self,
                "Rotate Box for Scan 2/2",
                "Width + Depth measured successfully!\n\n"
                "Rotate the box 90° so its HEIGHT faces the sensor,\n"
                "then click OK to begin the height scan."
            )

            # Send second newline → triggers getchar() for Measurement 2
            self.scan_proc.write(b'\n')
            self.status.setText("Scan 2/2 — measuring Height…")

    def _scan_read_stderr(self):
        data = bytes(self.scan_proc.readAllStandardError()).decode("utf-8", errors="replace")
        self._scan_stderr_buf += data

    def _scan_finished(self, exit_code, exit_status):
        self.scan_btn.setEnabled(True)

        if exit_status == QtCore.QProcess.CrashExit:
            QtWidgets.QMessageBox.critical(
                self, "Crash",
                f"LiDAR process crashed.\nSystem error: {self.scan_proc.errorString()}"
            )
            self.status.setText("Scan failed (crashed).")
            return

        stdout = self._scan_stdout_buf.strip()
        parsed = self._parse_lidar_result(stdout)

        if exit_code != 0 or not parsed:
            error_msg = (
                f"Process exited with code: {exit_code}\n\n"
                f"--- STDERR ---\n{self._scan_stderr_buf}\n\n"
                f"--- STDOUT ---\n{stdout}"
            )
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setWindowTitle("LiDAR Debug Log")
            msg_box.setText("The LiDAR process failed or returned invalid data.")
            msg_box.setDetailedText(error_msg)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.exec()
            self.status.setText(f"Process error (code {exit_code}). Click 'Show Details'.")
            return

        if parsed.get("status") != "ok":
            self.status.setText("Scan failed: status not 'ok'.")
            return

        # ------------------------------------------------------------------
        # Apply all three dimensions to the UI fields and update the 3-D box.
        # The C program stores:
        #   dims_in[0] = width  (first scan, face toward sensor)
        #   dims_in[1] = depth  (first scan, backstop method)
        #   dims_in[2] = height (second scan, box rotated 90°)
        #
        # app.py field mapping:
        #   length_edit → X (Width in visualiser)
        #   width_edit  → Y (Length/Depth in visualiser)
        #   height_edit → Z (Height in visualiser)
        # ------------------------------------------------------------------
        width_m  = float(parsed["width_mm"])  / 1000.0
        depth_m  = float(parsed["depth_mm"])  / 1000.0
        height_m = float(parsed["height_mm"]) / 1000.0

        self.length_edit.setText(f"{width_m:.3f}")
        self.width_edit.setText( f"{depth_m:.3f}")
        self.height_edit.setText(f"{height_m:.3f}")

        self.status.setText(
        f"Scan complete: W={width_m:.3f} m, D={depth_m:.3f} m, H={height_m:.3f} m"
        )
        self.on_add_box()

    # ------------------------------------------------------------------
    # JSON parser — accepts the new 3-key format from len_wid_addHeight.c
    # ------------------------------------------------------------------

    def _parse_lidar_result(self, stdout_text: str):
        """Search stdout lines in reverse for the last valid JSON object that
        contains at least 'status' and 'width_mm'."""
        if not stdout_text:
            return None
        for line in reversed(stdout_text.splitlines()):
            s = line.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    obj = json.loads(s)
                    if "status" in obj and "width_mm" in obj:
                        return obj
                except Exception:
                    pass
        return None


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()