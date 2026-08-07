import pytest

from acamp_robots.vision import MarkerVisionError, detect_markers, horizontal_error


class FakeAruco:
    DICT_APRILTAG_36h11 = 42

    @staticmethod
    def getPredefinedDictionary(identifier):
        assert identifier == 42
        return "dictionary"

    class ArucoDetector:
        def __init__(self, dictionary):
            assert dictionary == "dictionary"

        def detectMarkers(self, image):
            assert image == "image"
            return (
                [[[(10, 20), (30, 20), (30, 40), (10, 40)]]],
                [[7]],
                [],
            )


class FakeCV2:
    aruco = FakeAruco

    @staticmethod
    def imread(path):
        return "image" if path == "view.jpg" else None


def test_detect_markers_returns_json_serializable_geometry():
    markers = detect_markers("view.jpg", cv2_module=FakeCV2)
    assert markers == [{
        "id": 7,
        "center": [20.0, 30.0],
        "corners": [[10.0, 20.0], [30.0, 20.0], [30.0, 40.0], [10.0, 40.0]],
    }]
    assert horizontal_error(markers[0], image_width=400) == -180.0


def test_detect_markers_reports_missing_backend_and_bad_images():
    class NoAruco:
        @staticmethod
        def imread(path):
            return "image"

    with pytest.raises(MarkerVisionError, match="aruco"):
        detect_markers("view.jpg", cv2_module=NoAruco)
    with pytest.raises(MarkerVisionError, match="read image"):
        detect_markers("missing.jpg", cv2_module=FakeCV2)


def test_horizontal_error_rejects_invalid_width():
    with pytest.raises(ValueError):
        horizontal_error({"center": [1, 2]}, 0)
