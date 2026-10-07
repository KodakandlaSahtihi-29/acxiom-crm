from flask import Flask
from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    """Application factory for Acxiom CRM."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register models so SQLAlchemy metadata is aware of all entities
    from . import models  # noqa: F401

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.customer import customer_bp
    from app.routes.lead import lead_bp
    from app.routes.opportunity import opportunity_bp
    from app.routes.follow_up import follow_up_bp
    from app.routes.activity import activity_bp
    from app.routes.user import user_bp
    from app.routes.audit import audit_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(customer_bp)
    app.register_blueprint(lead_bp)
    app.register_blueprint(opportunity_bp)
    app.register_blueprint(follow_up_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(api_bp)

    csrf.exempt(api_bp)

    return app
