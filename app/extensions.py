try:
    from authlib.integrations.flask_client import OAuth
    _oauth = OAuth()
    OAUTH_AVAILABLE = True
except ImportError:
    _oauth = None
    OAUTH_AVAILABLE = False

google_oauth = None


def init_extensions(app):
    global google_oauth
    if not OAUTH_AVAILABLE or _oauth is None:
        return
    _oauth.init_app(app)
    google_oauth = _oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
