import u2lib


def test_package_exposes_modules():
    assert u2lib.__version__ == "0.5.0"
    for name in (
        "catalog",
        "dates",
        "features",
        "geo",
        "matching",
        "prediction",
        "quality",
        "setlist",
        "shows",
        "songs",
    ):
        assert hasattr(u2lib, name)
