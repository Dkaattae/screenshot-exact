"""The backend serves exactly the endpoints in ../openapi.yaml."""

from pathlib import Path

import yaml
from fastapi.routing import APIRoute

from app.main import create_app

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def contract_operations() -> set[tuple[str, str]]:
    spec = yaml.safe_load(CONTRACT.read_text())
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in METHODS
    }


def app_operations(settings) -> set[tuple[str, str]]:
    app = create_app(settings)
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
        for method in route.methods
        if method != "HEAD"
    }


def test_backend_matches_contract(settings):
    contract = contract_operations()
    served = app_operations(settings)
    assert contract - served == set(), "in the contract but not served"
    assert served - contract == set(), "served but not in the contract"


def test_contract_status_codes_match(settings):
    spec = yaml.safe_load(CONTRACT.read_text())
    app = create_app(settings)
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        for method in route.methods - {"HEAD"}:
            responses = spec["paths"][route.path][method.lower()]["responses"]
            success = {code for code in responses if code.startswith("2")}
            assert success == {str(route.status_code or 200)}, (method, route.path)
