"""Optional starting point for a camera-marker direction experiment."""
from acamp_robots.vision import detect_markers, horizontal_error


def observe_marker(image_path, image_width=400):
    markers = detect_markers(image_path)
    if not markers:
        return {"seen": False}
    marker = markers[0]
    return {
        "seen": True,
        "id": marker["id"],
        "horizontal_error_px": horizontal_error(marker, image_width),
    }
