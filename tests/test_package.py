import u2lib


def test_package_exposes_modules():
    assert u2lib.__version__ == "0.3.0"
    for name in ("dates", "geo", "matching", "quality", "shows", "songs"):
        assert hasattr(u2lib, name)
