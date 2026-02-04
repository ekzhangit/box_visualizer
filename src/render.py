import numpy as np
import pyqtgraph.opengl as gl


class BoxItem(gl.GLMeshItem):
    """
    A simple rectangular prism centered at origin, then translated to 'pos'.
    Dimensions: length=X, width=Y, height=Z
    """
    def __init__(self, length: float, width: float, height: float, pos=(0.0, 0.0, 0.0)):
        self.length = float(length)
        self.width = float(width)
        self.height = float(height)
        self.pos = np.array(pos, dtype=float)

        mesh = self._make_mesh(self.length, self.width, self.height)

        super().__init__(
            meshdata=mesh,
            smooth=False,
            drawFaces=True,
            color=(0.7, 0.45, 0.25, 1.0),   # brown-ish
            drawEdges=True,
            edgeColor=(0.0, 0.0, 0.0, 1.0),
        )

        self.setGLOptions("opaque")
        self._apply_transform()

    def _make_mesh(self, L: float, W: float, H: float) -> gl.MeshData:
        x = L / 2.0
        y = W / 2.0
        z = H / 2.0

        verts = np.array([
            [-x, -y, -z],
            [ x, -y, -z],
            [ x,  y, -z],
            [-x,  y, -z],
            [-x, -y,  z],
            [ x, -y,  z],
            [ x,  y,  z],
            [-x,  y,  z],
        ], dtype=float)

        faces = np.array([
            [0, 1, 2], [0, 2, 3],  # bottom
            [4, 5, 6], [4, 6, 7],  # top
            [0, 1, 5], [0, 5, 4],  # side
            [1, 2, 6], [1, 6, 5],  # side
            [2, 3, 7], [2, 7, 6],  # side
            [3, 0, 4], [3, 4, 7],  # side
        ], dtype=int)

        return gl.MeshData(vertexes=verts, faces=faces)

    def set_dimensions(self, length: float, width: float, height: float) -> None:
        self.length = float(length)
        self.width = float(width)
        self.height = float(height)

        self.setMeshData(meshdata=self._make_mesh(self.length, self.width, self.height))
        self._apply_transform()

    def move_by(self, dx: float, dy: float, dz: float) -> None:
        self.pos += np.array([dx, dy, dz], dtype=float)
        self._apply_transform()

    def _apply_transform(self) -> None:
        self.resetTransform()
        # IMPORTANT: call the parent class translate, NOT our own move method
        super().translate(float(self.pos[0]), float(self.pos[1]), float(self.pos[2]))
