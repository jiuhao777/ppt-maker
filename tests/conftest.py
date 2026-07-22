def pytest_configure(config):
    config.addinivalue_line("markers", "m0: M0 technical validation")
    config.addinivalue_line("markers", "office: requires Microsoft PowerPoint")
    config.addinivalue_line(
        "markers", "online: requires an explicitly configured API key"
    )
