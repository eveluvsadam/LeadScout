import pytest


@pytest.mark.parametrize("path", [
    "/", "/healthz", "/api/stats", "/api/categories", "/api/leads",
    "/export/csv", "/export/xlsx", "/static/style.css", "/admin",
])
def test_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_lead_pages_and_exports(client, lead):
    lid = lead["id"]
    page = client.get(f"/lead/{lid}")
    assert page.status_code == 200 and "Test Bakery" in page.text
    assert client.get(f"/lead/{lid}/demo").status_code == 200
    z = client.get(f"/lead/{lid}/demo.zip")
    assert z.headers["content-type"] == "application/zip"
    email = client.get(f"/lead/{lid}/email.txt")
    assert email.text.startswith("Subject: ")


def test_missing_lead_is_404(client):
    assert client.get("/lead/999999").status_code == 404


def test_batch_send_needs_mail_setup(client, lead):
    r = client.post("/send-batch", data={"lead_ids": [lead["id"]]})
    assert r.status_code == 200 and "SELLER_EMAIL_APP_PASSWORD" in r.text


def test_admin_setup_login_and_lockout(client):
    import app.main as m
    r = client.post("/admin/setup", data={"password": "secret12", "confirm": "secret12"},
                    follow_redirects=False)
    assert r.status_code == 303 and "admin_session" in r.cookies

    m._login_fails.clear()
    codes = [client.post("/admin/login", data={"password": "nope"}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429
    # Even the right password waits out the lockout.
    assert client.post("/admin/login", data={"password": "secret12"}).status_code == 429

    m._login_fails.clear()
    r = client.post("/admin/login", data={"password": "secret12"},
                    headers={"x-forwarded-proto": "https"}, follow_redirects=False)
    assert r.status_code == 303
    assert "secure" in r.headers["set-cookie"].lower()


def test_admin_actions_need_login():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anon:
        r = anon.post("/admin/delete-all", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
