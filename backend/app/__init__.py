from flask import Flask
from flask_cors import CORS
import logging

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
    
    # Enable CORS for React frontend
    CORS(app)
    
    # Register blueprints
    from app.routes.route_api import route_bp
    from app.routes.health import health_bp
    
    app.register_blueprint(route_bp, url_prefix='/api')
    app.register_blueprint(health_bp, url_prefix='/api')
    
    logger.info(f"Flask app created with config: {config_name}")
    
    return app
