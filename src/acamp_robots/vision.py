from __future__ import annotations

from pathlib import Path
from typing import Any


class MarkerVisionError(RuntimeError):
    pass


def _load_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise MarkerVisionError("OpenCV is not installed in this Python environment") from exc
    return cv2


def detect_markers(
    image_path: Path | str,
    dictionary: str = "DICT_APRILTAG_36h11",
    *,
    cv2_module=None,
) -> list[dict[str, Any]]:
    """Detect AprilTag-family markers through OpenCV's ArUco module."""
    cv2 = cv2_module or _load_cv2()
    aruco = getattr(cv2, "aruco", None)
    if aruco is None:
        raise MarkerVisionError(
            "OpenCV has no aruco module; install an OpenCV build with contrib modules"
        )
    dictionary_id = getattr(aruco, dictionary, None)
    if dictionary_id is None:
        raise MarkerVisionError(f"OpenCV does not provide marker dictionary {dictionary}")
    image = cv2.imread(str(image_path))
    if image is None:
        raise MarkerVisionError(f"Could not read image: {image_path}")
    marker_dictionary = aruco.getPredefinedDictionary(dictionary_id)
    if hasattr(aruco, "ArucoDetector"):
        corners, identifiers, _rejected = aruco.ArucoDetector(
            marker_dictionary
        ).detectMarkers(image)
    else:  # OpenCV 4.6 and earlier
        corners, identifiers, _rejected = aruco.detectMarkers(image, marker_dictionary)
    if identifiers is None:
        return []
    markers = []
    for identifier, marker_corners in zip(identifiers, corners):
        points = marker_corners[0] if len(marker_corners) == 1 else marker_corners
        normalized = [[float(x), float(y)] for x, y in points]
        markers.append(
            {
                "id": int(identifier[0]),
                "center": [
                    sum(point[0] for point in normalized) / len(normalized),
                    sum(point[1] for point in normalized) / len(normalized),
                ],
                "corners": normalized,
            }
        )
    return markers


def horizontal_error(marker: dict[str, Any], image_width: int | float) -> float:
    """Return marker-center pixels relative to the image center."""
    image_width = float(image_width)
    if image_width <= 0:
        raise ValueError("image_width must be positive")
    return float(marker["center"][0]) - image_width / 2
