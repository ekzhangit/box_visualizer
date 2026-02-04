from dataclasses import dataclass

@dataclass
class BoxDimensions:
    length: float  # X
    width: float   # Y
    height: float  # Z

    def validate(self) -> None:
        for name, v in (("length", self.length), ("width", self.width), ("height", self.height)):
            if v <= 0:
                raise ValueError(f"{name} must be > 0 (got {v})")
