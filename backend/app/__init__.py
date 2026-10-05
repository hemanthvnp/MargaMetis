from flask import Flask, request, make_response
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name='development'):
    app = Flask(__name__)

    db_url = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost/margametis')
    # Render provides 'postgres://' (legacy) — SQLAlchemy needs 'postgresql://'
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        return response

    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            resp = make_response()
            origin = request.headers.get('Origin')
            if origin:
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                resp.headers['Access-Control-Max-Age'] = '86400'
            resp.status_code = 204
            return resp

    from app.models import db
    db.init_app(app)

    with app.app_context():
        db.create_all()
        try:
            # Add result_json column if missing — keeps older DB deployments working
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('search_history')]
            if 'result_json' not in cols:
                db.session.execute(text('ALTER TABLE search_history ADD COLUMN result_json JSON NULL'))
                db.session.commit()
                logger.info('Added column search_history.result_json')
        except Exception as mig_err:
            logger.warning(f"Migration check failed: {mig_err}")

    from app.routes.route_api import route_bp
    from app.routes.health import health_bp
    from app.auth_api import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp

    app.register_blueprint(route_bp, url_prefix='/api')
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(user_bp, url_prefix='/api/user')

    logger.info(f"Flask app created ({config_name})")

    return app
