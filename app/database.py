import os
import ssl
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def database_settings():
    if os.getenv("MYSQL_HOST"):
        url = URL.create(
            "mysql+pymysql",
            username=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "defaultdb"),
        )
    else:
        url = make_url(os.getenv("DATABASE_URL", "sqlite:///./healthops.db"))
    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
    else:
        options.update(pool_size=3, max_overflow=2, pool_recycle=240)
    if url.get_backend_name() == "mysql":
        url = url.set(drivername="mysql+pymysql")
        # TLS cannot be disabled through a connection-string query parameter.
        url = url.set(query={})
        ca = os.getenv("MYSQL_SSL_CA", "")
        if not ca:
            raise RuntimeError("MYSQL_SSL_CA must contain the Aiven CA certificate PEM")
        context = ssl.create_default_context(cadata=ca)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        options["connect_args"] = {"ssl": context, "connect_timeout": 10, "charset": "utf8mb4"}
    return url, options


DATABASE_URL, engine_options = database_settings()
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
