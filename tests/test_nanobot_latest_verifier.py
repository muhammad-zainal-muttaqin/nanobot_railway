from scripts.verify_nanobot_latest import pinned_version


def test_dockerfile_pins_current_expected_nanobot_version():
    assert pinned_version() == "0.2.0"
