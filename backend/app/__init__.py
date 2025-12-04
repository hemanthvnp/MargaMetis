from flask import Flask
from flask_cors import CORS
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name='development'):
    """
    Application factory function to create Flask app instance.
    
    Args:
        config_name (str): Configuration environment
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 
        'mysql+pymysql://root:password@localhost/margametis'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Enable CORS for React/Vite frontend with credentials
    CORS(
        app,
        supports_credentials=True,
        origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # Session cookie settings for cross-origin dev
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False
    
    # Initialize database
    from app.models import db
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
        try:
            # Ensure search_history.result_json column exists (simple migration)
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('search_history')]
            if 'result_json' not in cols:
                # MySQL JSON column
                db.session.execute(text('ALTER TABLE search_history ADD COLUMN result_json JSON NULL'))
                db.session.commit()
                logger.info('Added column search_history.result_json')
        except Exception as mig_err:
            logger.warning(f"Migration check failed: {mig_err}")
    
    # Register blueprints
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
    
    logger.info(f"Flask app created with config: {config_name}")
    
    return app
