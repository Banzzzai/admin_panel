import os

class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    )

    KEYCLOAK_URL = os.environ["KEYCLOAK_URL"]
    KEYCLOAK_REALM = os.environ["KEYCLOAK_REALM"]
    KEYCLOAK_CLIENT_ID = os.environ["KEYCLOAK_CLIENT_ID"]
    KEYCLOAK_CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
    KEYCLOAK_REDIRECT_URI = os.environ["KEYCLOAK_REDIRECT_URI"]

    KEYCLOAK_ADMIN_CLIENT_ID = os.environ["KEYCLOAK_ADMIN_CLIENT_ID"]
    KEYCLOAK_ADMIN_CLIENT_SECRET = os.environ["KEYCLOAK_ADMIN_CLIENT_SECRET"]

    KEYCLOAK_ADMIN_ROLE = os.environ.get("KEYCLOAK_ADMIN_ROLE", "admin-panel-admin")
    KEYCLOAK_DEFAULT_ROLE = os.environ.get("KEYCLOAK_DEFAULT_ROLE", "viewer")