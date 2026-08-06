from acamp_robots.cli import parse_call_arg


def test_call_arguments_accept_plain_strings_and_paths():
    assert parse_call_arg("view.jpg") == "view.jpg"
    assert parse_call_arg("forward") == "forward"


def test_call_arguments_still_accept_json_values():
    assert parse_call_arg("1.5") == 1.5
    assert parse_call_arg("true") is True
    assert parse_call_arg("[1, 2, 3]") == [1, 2, 3]
