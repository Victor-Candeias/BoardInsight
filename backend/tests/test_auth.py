import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from ldap3.core.exceptions import LDAPSocketOpenError

from app.api.v1.auth import SESSION_COOKIE, get_directory
from app.core.config import ConfigurationError, get_settings
from app.core.database import get_database
from app.main import create_app
from app.repositories.auth_sessions import AuthSessionRepository, token_id
from app.repositories.base import utcnow
from app.services.auth import (
    AccessDenied,
    AuthUser,
    DirectoryUnavailable,
    InvalidCredentials,
    LdapDirectory,
    ldap_server_urls,
)

PASSWORD = "S3gredo!Muito-Secreto"
USER_DN = "CN=Ana Silva,OU=Users,DC=w2k,DC=ctt,DC=pt"
GROUP_DN = "CN=GG-BoardInsight,OU=Groups,DC=w2k,DC=ctt,DC=pt"


class FakeConnection:
    """Simula o AD: bind com password correta e pesquisas de utilizador, grupo e pertença (in-chain)."""

    def __init__(self, ad, user, password):
        self.ad, self.user, self.password = ad, user, password
        self.result, self.response = {}, None

    def bind(self):
        self.ad.binds.append(self.user)
        if self.ad.passwords.get(self.user) == self.password:
            self.result = {"result": 0}
            return True
        self.result = {"result": 49, "description": "invalidCredentials", "message": "80090308: LdapErr: data 52e"}
        return False

    def search(self, base, search_filter, scope="SUBTREE", attributes=None):
        self.ad.searches.append((base, search_filter, scope))
        self.response = []
        if "objectClass=group" in search_filter and "GG-BoardInsight" in search_filter:
            self.response = [{"type": "searchResEntry", "dn": GROUP_DN, "attributes": {"cn": "GG-BoardInsight"}}]
        elif "memberOf:1.2.840.113556.1.4.1941:=" in search_filter:
            if base == USER_DN and self.ad.member and GROUP_DN in search_filter:
                self.response = [{"type": "searchResEntry", "dn": USER_DN, "attributes": {}}]
        elif "ana.silva@ctt.pt" in search_filter:
            attrs = {"displayName": "Ana Silva", "mail": "ana.silva@ctt.pt", "userPrincipalName": "ana.silva@w2k.ctt.pt"}
            self.response = [{"type": "searchResEntry", "dn": USER_DN, "attributes": attrs}]
        return bool(self.response)

    def unbind(self):
        return True


class FakeAD:
    def __init__(self, member=True, down=False):
        self.member, self.down = member, down
        self.passwords = {"ana.silva@ctt.pt": PASSWORD, USER_DN: PASSWORD, "svc-boardinsight": "svc-pass"}
        self.binds, self.searches = [], []

    def __call__(self, user, password):
        if self.down:
            raise LDAPSocketOpenError("socket connection error")
        return FakeConnection(self, user, password)


@pytest.fixture
def auth_settings(settings):
    settings.auth_enabled = True
    settings.ldap_domain = "w2k.ctt.pt"
    return settings


def directory(settings, ad):
    return LdapDirectory(settings, connection_factory=ad)


def test_authenticate_binds_with_email_and_reads_profile(auth_settings):
    ad = FakeAD()
    user = directory(auth_settings, ad).authenticate(" ana.silva@ctt.pt ", PASSWORD)
    assert user == AuthUser(username="ana.silva@w2k.ctt.pt", name="Ana Silva", email="ana.silva@ctt.pt")
    assert ad.binds == ["ana.silva@ctt.pt"]
    assert ad.searches[0][0] == "DC=w2k,DC=ctt,DC=pt"


@pytest.mark.parametrize("email,password", [("ana.silva@ctt.pt", "errada"), ("ana.silva@ctt.pt", ""), ("ana.silva", PASSWORD)])
def test_authenticate_rejects_bad_credentials(auth_settings, email, password):
    ad = FakeAD()
    with pytest.raises(InvalidCredentials):
        directory(auth_settings, ad).authenticate(email, password)
    # Password vazia (bind não autenticado aceite pelo AD) e emails inválidos nunca chegam ao domínio.
    assert ad.binds == ([] if not password or "@" not in email else [email])


def test_authenticate_checks_nested_group_membership(auth_settings):
    auth_settings.auth_allowed_group = "GG-BoardInsight"
    assert directory(auth_settings, FakeAD(member=True)).authenticate("ana.silva@ctt.pt", PASSWORD).name == "Ana Silva"
    ad = FakeAD(member=False)
    with pytest.raises(AccessDenied):
        directory(auth_settings, ad).authenticate("ana.silva@ctt.pt", PASSWORD)
    membership = [s for s in ad.searches if "memberOf" in s[1]]
    assert membership == [(USER_DN, f"(memberOf:1.2.840.113556.1.4.1941:={GROUP_DN})", "BASE")]


def test_authenticate_with_service_account_binds_as_user_dn(auth_settings):
    auth_settings.ldap_bind_user = "svc-boardinsight"
    auth_settings.ldap_bind_password = SecretStr("svc-pass")
    ad = FakeAD()
    assert directory(auth_settings, ad).authenticate("ana.silva@ctt.pt", PASSWORD).email == "ana.silva@ctt.pt"
    assert ad.binds == ["svc-boardinsight", USER_DN]
    with pytest.raises(InvalidCredentials):
        directory(auth_settings, FakeAD()).authenticate("outro@ctt.pt", PASSWORD)


def test_search_filters_escape_the_email(auth_settings):
    auth_settings.ldap_bind_user = "svc-boardinsight"
    auth_settings.ldap_bind_password = SecretStr("svc-pass")
    ad = FakeAD()
    with pytest.raises(InvalidCredentials):
        directory(auth_settings, ad).authenticate("*)(mail=*@ctt.pt", PASSWORD)
    assert "\\2a\\29\\28mail=\\2a@ctt.pt" in ad.searches[0][1]


def test_directory_unreachable_is_reported_as_unavailable(auth_settings):
    with pytest.raises(DirectoryUnavailable):
        directory(auth_settings, FakeAD(down=True)).authenticate("ana.silva@ctt.pt", PASSWORD)


def test_real_ldap3_connection_failure_is_unavailable(auth_settings):
    auth_settings.ldap_url = "ldaps://127.0.0.1:1"
    auth_settings.ldap_timeout_seconds = 1
    with pytest.raises(DirectoryUnavailable):
        LdapDirectory(auth_settings).authenticate("ana.silva@ctt.pt", PASSWORD)


def test_server_urls_from_config_dns_or_domain(auth_settings):
    auth_settings.ldap_url = "ldaps://dc1.w2k.ctt.pt, ldap://dc2.w2k.ctt.pt:389"
    assert ldap_server_urls(auth_settings) == ["ldaps://dc1.w2k.ctt.pt", "ldap://dc2.w2k.ctt.pt:389"]
    auth_settings.ldap_url = ""
    assert ldap_server_urls(auth_settings, lambda d: ["dc1." + d]) == ["ldaps://dc1.w2k.ctt.pt:636"]
    assert ldap_server_urls(auth_settings, lambda d: []) == ["ldaps://w2k.ctt.pt:636"]
    auth_settings.ldap_url = "http://dc1"
    with pytest.raises(ConfigurationError):
        ldap_server_urls(auth_settings)
    auth_settings.ldap_url = auth_settings.ldap_domain = ""
    with pytest.raises(ConfigurationError):
        ldap_server_urls(auth_settings)


@pytest.fixture
def ad():
    return FakeAD()


@pytest.fixture
def auth_client(db, auth_settings, ad):
    app = create_app(init_db=False, settings=auth_settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_settings] = lambda: auth_settings
    app.dependency_overrides[get_directory] = lambda: directory(auth_settings, ad)
    with TestClient(app) as client:
        yield client


def login(client, password=PASSWORD, email="ana.silva@ctt.pt"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_api_is_open_when_auth_is_disabled(client):
    assert client.get("/api/v1/boards").status_code == 200
    assert client.get("/api/v1/auth/me").json() == {"authEnabled": False, "user": None}
    assert login(client).status_code == 404


def test_api_requires_session_and_login_sets_cookie(auth_client, db):
    response = auth_client.get("/api/v1/boards")
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthenticated"
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    assert auth_client.get("/health").status_code == 200

    response = login(auth_client)
    assert response.status_code == 200
    assert response.json() == {
        "authEnabled": True,
        "user": {"username": "ana.silva@w2k.ctt.pt", "name": "Ana Silva", "email": "ana.silva@ctt.pt"},
    }
    cookie = response.headers["set-cookie"]
    assert SESSION_COOKIE in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=86400" in cookie
    token = auth_client.cookies[SESSION_COOKIE]
    stored = db["auth_sessions"].find_one()
    assert stored["_id"] == token_id(token) and token not in str(stored)

    assert auth_client.get("/api/v1/boards").status_code == 200
    assert auth_client.get("/api/v1/auth/me").json()["user"]["name"] == "Ana Silva"


def test_logout_invalidates_session(auth_client, db):
    login(auth_client)
    token = auth_client.cookies[SESSION_COOKIE]
    assert auth_client.post("/api/v1/auth/logout").status_code == 204
    assert db["auth_sessions"].count_documents({}) == 0
    auth_client.cookies.set(SESSION_COOKIE, token)
    assert auth_client.get("/api/v1/boards").status_code == 401


def test_expired_session_is_rejected(auth_client, db):
    login(auth_client)
    db["auth_sessions"].update_many({}, {"$set": {"expiresAt": utcnow() - timedelta(seconds=1)}})
    assert auth_client.get("/api/v1/boards").status_code == 401


def test_session_idle_expiry_slides_but_not_past_absolute_limit(db):
    repo = AuthSessionRepository(db)
    token = repo.create(AuthUser("u", "U", "u@ctt.pt"), timedelta(minutes=30), timedelta(hours=1))
    stale, absolute = utcnow() - timedelta(minutes=50), utcnow() + timedelta(minutes=10)
    db["auth_sessions"].update_one({}, {"$set": {"lastSeenAt": stale, "absoluteExpiresAt": absolute}})
    assert repo.get(token, timedelta(minutes=30)) is not None
    doc = db["auth_sessions"].find_one()
    assert doc["expiresAt"] == doc["absoluteExpiresAt"]
    assert repo.get("token-inventado", timedelta(minutes=30)) is None


@pytest.mark.parametrize(
    "ad_kwargs,group,status,code",
    [
        ({"member": False}, "GG-BoardInsight", 403, "forbidden"),
        ({"down": True}, "", 503, "directory_unavailable"),
    ],
)
def test_login_errors(auth_client, auth_settings, ad, ad_kwargs, group, status, code):
    vars(ad).update(ad_kwargs)
    auth_settings.auth_allowed_group = group
    response = login(auth_client)
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert SESSION_COOKIE not in auth_client.cookies


def test_failed_logins_are_limited(auth_client, auth_settings):
    auth_settings.auth_max_failed_logins = 3
    for _ in range(3):
        response = login(auth_client, password="errada")
        assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_credentials"
    blocked = login(auth_client)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "too_many_attempts"
    assert 1 <= int(blocked.headers["retry-after"]) <= 900
    # O limite também se aplica por IP, com outros emails.
    assert login(auth_client, email="outra@ctt.pt").status_code == 429


def test_successful_login_resets_email_failures(auth_client, auth_settings):
    auth_settings.auth_max_failed_logins = 3
    login(auth_client, password="errada")
    login(auth_client, password="errada")
    assert login(auth_client).status_code == 200
    assert login(auth_client, password="errada", email="ANA.SILVA@ctt.pt").status_code == 401


def test_password_never_reaches_logs_or_responses(auth_client, caplog):
    caplog.set_level(logging.DEBUG)
    responses = [login(auth_client, password="errada-" + PASSWORD), login(auth_client)]
    responses.append(auth_client.post("/api/v1/auth/login", json={"email": "ana.silva@ctt.pt", "password": 123}))
    assert PASSWORD not in caplog.text
    assert all(PASSWORD not in r.text for r in responses)
    assert any(getattr(r, "login", None) == "ana.silva@w2k.ctt.pt" for r in caplog.records)
