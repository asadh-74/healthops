import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from app.database import Base, database_settings


def test_all_tables_compile_for_mysql():
    for table in Base.metadata.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=mysql.dialect()))


def test_mysql_requires_ca(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "example.aivencloud.com")
    monkeypatch.setenv("MYSQL_USER", "demo")
    monkeypatch.setenv("MYSQL_PASSWORD", "not-real")
    monkeypatch.delenv("MYSQL_SSL_CA", raising=False)
    with pytest.raises(RuntimeError, match="CA certificate"):
        database_settings()


def test_mysql_verifies_tls_and_preserves_password(monkeypatch):
    import ssl

    monkeypatch.setenv("MYSQL_HOST", "example.aivencloud.com")
    monkeypatch.setenv("MYSQL_USER", "demo")
    monkeypatch.setenv("MYSQL_PASSWORD", "demo:@/?special")
    monkeypatch.setenv("MYSQL_SSL_CA", "test-placeholder")
    monkeypatch.setattr(
        ssl, "create_default_context", lambda **kwargs: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    )
    url, options = database_settings()
    assert url.password == "demo:@/?special"
    assert options["connect_args"]["ssl"].check_hostname is True
    assert options["connect_args"]["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert options["pool_size"] + options["max_overflow"] == 5
