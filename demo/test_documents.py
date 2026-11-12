import sys

import pytest
from django.conf import settings
from django.test import Client
from django.urls import Resolver404, resolve

URL = "/demo/documents/"
FORM = {
    "title": "训练总结",
    "content_format": "markdown",
    "template_id": "formal",
    "content": "## 中文正文\n\n![拓扑](tms-asset:topology)",
}


def test_production_does_not_register_document_demo():
    if settings.DEBUG:
        pytest.skip("Production route check runs with DEBUG=False.")
    with pytest.raises(Resolver404):
        resolve(URL)


@pytest.fixture
def document_client(django_user_model):
    if not settings.DEBUG:
        pytest.skip("Demo endpoint tests require process startup with DEBUG=True.")
    user = django_user_model.objects.create_user(username="document-demo")
    client = Client(enforce_csrf_checks=True)
    assert client.get(URL).status_code == 302
    client.force_login(user)
    page = client.get(URL)
    assert page.status_code == 200
    assert b'sandbox="allow-same-origin"' in page.content
    assert "unsafe-inline" not in page["Content-Security-Policy"]
    assert client.post(URL, {**FORM, "action": "html"}).status_code == 403
    client.defaults["HTTP_X_CSRFTOKEN"] = client.cookies["csrftoken"].value
    return client


@pytest.mark.django_db
def test_demo_previews_html_with_private_headers(document_client):
    response = document_client.post(URL, {**FORM, "action": "html"})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "中文正文" in response.content.decode()
    assert b"data:image/png;base64," in response.content
    assert b"formal.css" in response.content


@pytest.mark.django_db
def test_demo_reports_errors_and_wraps_pdf(document_client, monkeypatch):
    response = document_client.post(
        URL,
        {**FORM, "template_id": "unknown", "action": "preview"},
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 400
    assert "template_id" in response.json()["fields"]

    monkeypatch.setattr("demo.documents.generate_document_pdf", lambda document: b"%PDF-")
    for action, disposition in (("preview", "inline"), ("download", "attachment")):
        response = document_client.post(URL, {**FORM, "action": action})
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith(f"{disposition}; filename*=utf-8''")
        assert response["Cache-Control"] == "private, no-store"
        assert response.content == b"%PDF-"


@pytest.mark.django_db
@pytest.mark.document_pdf_native
@pytest.mark.skipif(sys.platform != "linux", reason="PDF rendering requires Linux and Noto CJK")
def test_demo_post_produces_real_pdf(document_client):
    response = document_client.post(URL, {**FORM, "action": "preview"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
