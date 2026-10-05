import pytest

from app import cache as redis_cache


pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/auth/logout"),
        ("post", "/api/route/calculate"),
        ("put", "/api/user/history/1"),
        ("delete", "/api/user/history/1"),
    ],
)
def test_mutating_request_requires_csrf_token_even_without_origin(client, method, path):
    response = getattr(client, method)(path, headers={"X-CSRFToken": ""})

    assert response.status_code == 403


def test_mutating_request_accepts_session_csrf_token(client):
    token = client.get("/api/auth/me").get_json()["csrf_token"]
    response = client.post(
        "/api/auth/logout",
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == 200


def test_cors_preflight_allows_csrf_header(client):
    response = client.options(
        "/api/auth/login",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "X-CSRFToken" in response.headers["Access-Control-Allow-Headers"]


def test_cors_does_not_expose_csrf_token_to_untrusted_origins(client):
    response = client.get(
        "/api/auth/me",
        headers={"Origin": "https://evil.example"},
    )

    assert "Access-Control-Allow-Origin" not in response.headers


def test_sixth_auth_attempt_is_limited_and_window_is_not_extended(client, monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.counts = {}
            self.expirations = []

        def incr(self, key):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

        def expire(self, key, seconds):
            self.expirations.append((key, seconds))
            return True

    redis = FakeRedis()
    monkeypatch.setattr(redis_cache, "_redis", lambda: redis)
    headers = {
        "X-CSRFToken": client.get("/api/auth/me").get_json()["csrf_token"],
        "X-Forwarded-For": "198.51.100.23",
    }

    responses = [
        client.post(
            "/api/auth/login",
            json={"username": "missing", "password": "incorrect"},
            headers=headers,
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [
        401, 401, 401, 401, 401, 429,
    ]
    assert list(redis.counts) == ["auth:login:198.51.100.23"]
    assert redis.expirations == [("auth:login:198.51.100.23", 60)]
