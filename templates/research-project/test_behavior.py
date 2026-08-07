from behavior import run_trial


class FakeRobot:
    def status(self):
        return {"robot": "test-double", "moving": False}


def test_starter_trial_never_moves_hardware():
    result = run_trial(FakeRobot())
    assert result["before"]["moving"] is False
    assert "No movement" in result["observation"]
