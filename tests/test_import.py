def test_import_package():
    import talon

    assert hasattr(talon, "__version__")
