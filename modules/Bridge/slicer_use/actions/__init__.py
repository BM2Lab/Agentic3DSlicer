# Import all action modules so their @ns.action() decorators run and
# populate the global controller registry on first import.
from . import (  # noqa: F401
    crop,
    histogram,
    io,
    markup,
    model,
    scene,
    segment_editor,
    segmentation,
    transform,
    visualization,
    volume,
)
