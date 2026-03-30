from app.api.deps import PaginationParams


def test_pagination_params_defaults():
    params = PaginationParams()
    assert params.skip == 0
    assert params.limit == 50


def test_pagination_params_custom():
    params = PaginationParams(skip=10, limit=20)
    assert params.skip == 10
    assert params.limit == 20


def test_pagination_params_limit_capped():
    """limit above 200 should be rejected by FastAPI Query validation."""
    from typing import Annotated

    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/items")
    async def list_items(p: Annotated[PaginationParams, Depends()]):
        return {"skip": p.skip, "limit": p.limit}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/items?limit=9999")
    assert resp.status_code == 422
