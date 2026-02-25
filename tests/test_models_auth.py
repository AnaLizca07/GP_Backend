def test_models_package_exists():
    import app.models
    assert app.models is not None