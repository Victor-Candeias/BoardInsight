"""Autenticação com email e password do domínio (G9).

As credenciais são validadas no Active Directory com um *simple bind* sobre LDAPS (ou StartTLS): nunca há
bind sem TLS e o certificado do DC é sempre validado (CA de `LDAP_CA_FILE` ou do repositório do sistema).
A password só é usada no bind: não é guardada, registada em logs nem devolvida em erros.
"""

import logging
import re
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import ConfigurationError, Settings

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Regra LDAP_MATCHING_RULE_IN_CHAIN: inclui grupos aninhados.
IN_CHAIN = "1.2.840.113556.1.4.1941"
INVALID_CREDENTIALS = 49
USER_ATTRIBUTES = ["displayName", "mail", "userPrincipalName"]


class AuthError(Exception):
    status = 401
    code = "invalid_credentials"
    message = "credenciais inválidas"


class InvalidCredentials(AuthError):
    pass


class AccessDenied(AuthError):
    status = 403
    code = "forbidden"
    message = "sem permissão para aceder ao BoardInsight"


class DirectoryUnavailable(AuthError):
    status = 503
    code = "directory_unavailable"
    message = "não foi possível contactar o domínio; confirme a ligação à rede da empresa (ou VPN)"


@dataclass(frozen=True)
class AuthUser:
    username: str
    name: str
    email: str

    def to_api(self) -> dict[str, str]:
        return {"username": self.username, "name": self.name, "email": self.email}


class Directory(Protocol):
    def authenticate(self, email: str, password: str) -> AuthUser: ...


class LdapConnection(Protocol):
    """Subconjunto de `ldap3.Connection` usado aqui (substituído nos testes)."""

    result: dict[str, Any]
    response: list[dict[str, Any]] | None

    def bind(self) -> bool: ...
    def search(self, search_base: str, search_filter: str, search_scope: str = ..., attributes: Any = ...) -> bool: ...
    def unbind(self) -> bool: ...


ConnectionFactory = Callable[[str, str], LdapConnection]


def discover_domain_controllers(domain: str) -> list[str]:
    """DCs do domínio pelo registo DNS SRV `_ldap._tcp.dc._msdcs.<domínio>` (por prioridade e peso)."""
    try:
        import dns.resolver

        answers = dns.resolver.resolve(f"_ldap._tcp.dc._msdcs.{domain}", "SRV", lifetime=3)
    except Exception as exc:  # noqa: BLE001 - sem DNS do domínio usa-se o nome do domínio
        logger.info("descoberta de DCs por DNS SRV falhou", extra={"domain": domain, "error": type(exc).__name__})
        return []
    records = sorted(answers, key=lambda r: (r.priority, -r.weight))
    return [str(r.target).rstrip(".") for r in records]


def ldap_server_urls(settings: Settings, discover: Callable[[str], list[str]] = discover_domain_controllers) -> list[str]:
    urls = [u.strip() for u in settings.ldap_url.split(",") if u.strip()]
    if not urls:
        domain = settings.ldap_domain.strip()
        if not domain:
            raise ConfigurationError("com AUTH_ENABLED=true é preciso definir LDAP_URL ou LDAP_DOMAIN no .env")
        urls = [f"ldaps://{host}:636" for host in discover(domain)] or [f"ldaps://{domain}:636"]
    for url in urls:
        if not url.lower().startswith(("ldaps://", "ldap://")):
            raise ConfigurationError(f"LDAP_URL inválido (usar ldaps:// ou ldap:// com StartTLS): {url}")
    return urls


def ldap3_connection_factory(settings: Settings) -> ConnectionFactory:
    """Abre ligações TLS aos DCs (ldaps:// direto; ldap:// com StartTLS obrigatório antes do bind)."""
    from ldap3 import FIRST, SIMPLE, Connection, Server, ServerPool, Tls

    tls = Tls(
        validate=ssl.CERT_REQUIRED,
        ca_certs_file=str(settings.ldap_ca_file) if settings.ldap_ca_file else None,
    )
    servers = [
        Server(url, use_ssl=url.lower().startswith("ldaps://"), tls=tls, connect_timeout=settings.ldap_timeout_seconds)
        for url in ldap_server_urls(settings)
    ]
    pool = ServerPool(servers, FIRST, active=1, exhaust=False)

    def connect(user: str, password: str) -> LdapConnection:
        conn = Connection(
            pool,
            user=user,
            password=password,
            authentication=SIMPLE,
            read_only=True,
            auto_referrals=False,
            receive_timeout=settings.ldap_timeout_seconds,
        )
        conn.open(read_server_info=False)
        if not conn.server.ssl and not conn.start_tls(read_server_info=False):
            conn.unbind()
            raise DirectoryUnavailable()
        return conn

    return connect


def escape_filter(value: str) -> str:
    from ldap3.utils.conv import escape_filter_chars

    return escape_filter_chars(value)


def _entries(conn: LdapConnection) -> list[tuple[str, dict[str, Any]]]:
    return [(r["dn"], r.get("attributes", {})) for r in (conn.response or []) if r.get("type") == "searchResEntry"]


def _first(value: Any) -> str:
    if isinstance(value, list | tuple):
        value = value[0] if value else ""
    return str(value or "")


class LdapDirectory:
    def __init__(self, settings: Settings, connection_factory: ConnectionFactory | None = None):
        self.settings = settings
        self._factory = connection_factory

    @property
    def factory(self) -> ConnectionFactory:
        if self._factory is None:
            self._factory = ldap3_connection_factory(self.settings)
        return self._factory

    def authenticate(self, email: str, password: str) -> AuthUser:
        email = email.strip()
        # Em AD, um bind com password vazia é "não autenticado" e é aceite: recusar antes.
        if not EMAIL_RE.match(email) or not password:
            raise InvalidCredentials()
        from ldap3.core.exceptions import LDAPException

        try:
            login = self._login_name(email)
            conn = self.factory(login, password)
            try:
                if not conn.bind():
                    self._raise_bind_error(conn, email)
                return self._authorize(conn, email)
            finally:
                conn.unbind()
        except LDAPException as exc:
            logger.warning("domínio indisponível no login", extra={"error": type(exc).__name__})
            raise DirectoryUnavailable() from None

    def _login_name(self, email: str) -> str:
        """Nome usado no bind: o email como UPN ou, com conta de serviço, o DN encontrado pelo `mail`."""
        if not self.settings.ldap_bind_user:
            return email
        password = self.settings.ldap_bind_password.get_secret_value() if self.settings.ldap_bind_password else ""
        conn = self.factory(self.settings.ldap_bind_user, password)
        try:
            if not conn.bind():
                logger.error("conta de serviço LDAP recusada", extra={"ldap_result": conn.result.get("result")})
                raise DirectoryUnavailable()
            entry = self._find_user(conn, email)
        finally:
            conn.unbind()
        if entry is None:
            raise InvalidCredentials()
        return entry[0]

    def _raise_bind_error(self, conn: LdapConnection, email: str) -> None:
        result = conn.result or {}
        if result.get("result") == INVALID_CREDENTIALS:
            # O AD indica a causa em "data XXX" (52e password errada, 775 conta bloqueada, 532 password expirada).
            reason = re.search(r"data ([0-9a-f]+)", str(result.get("message", "")))
            logger.info("bind LDAP recusado", extra={"login": email, "ad_reason": reason.group(1) if reason else None})
            raise InvalidCredentials()
        logger.warning("bind LDAP falhou", extra={"ldap_result": result.get("result"), "ldap_description": result.get("description")})
        raise DirectoryUnavailable()

    def _find_user(self, conn: LdapConnection, email: str) -> tuple[str, dict[str, Any]] | None:
        value = escape_filter(email)
        conn.search(
            self.settings.ldap_search_base,
            f"(&(objectCategory=person)(objectClass=user)(|(userPrincipalName={value})(mail={value})))",
            "SUBTREE",
            attributes=USER_ATTRIBUTES,
        )
        entries = _entries(conn)
        return entries[0] if entries else None

    def _authorize(self, conn: LdapConnection, email: str) -> AuthUser:
        entry = self._find_user(conn, email)
        group = self.settings.auth_allowed_group.strip()
        if entry is None:
            if group:
                logger.warning("utilizador autenticado mas não encontrado no diretório", extra={"login": email})
                raise AccessDenied()
            return AuthUser(username=email, name=email, email=email)
        dn, attrs = entry
        user = AuthUser(
            username=_first(attrs.get("userPrincipalName")) or email,
            name=_first(attrs.get("displayName")) or email,
            email=_first(attrs.get("mail")) or email,
        )
        if group and not self._is_member(conn, dn, group):
            logger.info("utilizador fora do grupo autorizado", extra={"login": user.username})
            raise AccessDenied()
        return user

    def _is_member(self, conn: LdapConnection, user_dn: str, group: str) -> bool:
        group_dn = group if "=" in group else self._group_dn(conn, group)
        if group_dn is None:
            logger.error("grupo AUTH_ALLOWED_GROUP não encontrado no diretório", extra={"group": group})
            return False
        conn.search(user_dn, f"(memberOf:{IN_CHAIN}:={escape_filter(group_dn)})", "BASE", attributes=["cn"])
        return bool(_entries(conn))

    def _group_dn(self, conn: LdapConnection, name: str) -> str | None:
        value = escape_filter(name)
        conn.search(
            self.settings.ldap_search_base,
            f"(&(objectClass=group)(|(cn={value})(sAMAccountName={value})))",
            "SUBTREE",
            attributes=["cn"],
        )
        entries = _entries(conn)
        return entries[0][0] if entries else None
