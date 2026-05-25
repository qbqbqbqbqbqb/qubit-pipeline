import pytest
from src.qubit.core.app import App


def test_app_is_minimal_container():
    app = App()
    assert app.services == []
    assert app.state is None
    assert app.event_bus is None
    assert app.server is None


def test_app_add_service():
    app = App()
    svc = object()
    app.add_service(svc)
    assert svc in app.services
    assert len(app.services) == 1


def test_app_add_multiple_services():
    app = App()
    s1, s2 = object(), object()
    app.add_service(s1)
    app.add_service(s2)
    assert s1 in app.services
    assert s2 in app.services
    assert len(app.services) == 2
