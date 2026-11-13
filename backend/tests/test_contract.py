"""The backend serves exactly the endpoints in ../openapi.yaml, with the same success codes."""

from pathlib import Path

import yaml

from app.main import create_app

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def operations(spec: dict) -> dict[tuple[str, str], set[str]]:
    """(METHOD, path) -> the operation's 2xx status codes."""
    return {
        (method.upper(), path): {code for code in operation["responses"] if code.startswith("2")}
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }


def test_backend_matches_contract(settings):
    contract = operations(yaml.safe_load(CONTRACT.read_text()))
    served = operations(create_app(settings).openapi())
    assert sorted(set(contract) - set(served)) == [], "in the contract but not served"
    assert sorted(set(served) - set(contract)) == [], "served but not in the contract"
    for operation, codes in contract.items():
        assert served[operation] == codes, operation
