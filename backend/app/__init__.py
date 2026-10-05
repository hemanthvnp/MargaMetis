import hmac
import logging
import os

from flask import Flask, jsonify, request, make_response, session
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
migrate = Migrate()


def create_app(config_name='development'):
    app = Flask(__name__)

    try:
        trusted_proxy_count = int(os.getenv('TRUSTED_PROXY_COUNT', '0'))
    except ValueError as exc:
        raise RuntimeError('TRUSTED_PROXY_COUNT must be a non-negative integer') from exc
    if trusted_proxy_count < 0:
        raise RuntimeError('TRUSTED_PROXY_COUNT must be a non-negative integer')
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxy_count)

    db_url = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost/margametis')
    # Render provides 'postgres://' (legacy) — SQLAlchemy needs 'postgresql://'
    if 'DATABASE_URL' not in os.environ:
        db_url = 'sqlite:///margametis.db'
    # Name the psycopg2 driver explicitly: SQLAlchemy 2.1+ defaults a bare
    # 'postgresql://' to psycopg3, which this image does not install.
    for legacy in ('postgres://', 'postgresql://'):
        if db_url.startswith(legacy):
            db_url = 'postgresql+psycopg2://' + db_url[len(legacy):]
            break
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    if db_url.startswith('postgresql'):
        # One sync gunicorn worker serves everything, so a runaway query would
        # freeze the whole service (and Render's proxy drops the response, which
        # the browser reports as a CORS error). Fail it after 60 s instead.
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'connect_args': {'options': '-c statement_timeout=60000'},
        }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MIGRATIONS_DIR'] = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'migrations')
    )
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True

    _base = [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3030", "http://127.0.0.1:3030",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ]
    _extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    allowed_origins = set(_base + _extra)

    @app.after_request
    def add_cors(response):
        origin = request.headers.get('Origin')
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers.add('Vary', 'Origin')
        return response

    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            resp = make_response()
            origin = request.headers.get('Origin')
            if origin in allowed_origins:
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                resp.headers['Access-Control-Max-Age'] = '86400'
                resp.headers.add('Vary', 'Origin')
            resp.status_code = 204
            return resp

    @app.before_request
    def enforce_csrf():
        if request.method not in {'POST', 'PUT', 'DELETE'}:
            return None
        expected = session.get('_csrf_token')
        supplied = request.headers.get('X-CSRFToken', '')
        if not expected or not supplied or not hmac.compare_digest(
            str(expected), str(supplied)
        ):
            return jsonify({'error': 'CSRF validation failed'}), 403
        return None

    from app.models import db
    db.init_app(app)
    migrate.init_app(app, db, directory=app.config['MIGRATIONS_DIR'])

    from app.routes.route_api import route_bp
    from app.routes.health import health_bp
    from app.auth_api import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp
    from app.routes.spatial import spatial_bp

    app.register_blueprint(route_bp, url_prefix='/api')
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(spatial_bp, url_prefix='/api/spatial')

    logger.info(f"Flask app created ({config_name})")

    return app
