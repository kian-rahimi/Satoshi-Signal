from app.main import health


def test_health():
    response = health()
    assert response["status"] == "ok"
    assert response["service"] == "Satoshi's Crystal Ball"

