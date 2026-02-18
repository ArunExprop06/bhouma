from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)

    # Ensure upload folder exists
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register blueprints
    from app_package.routes.auth import auth_bp
    from app_package.routes.dashboard import dashboard_bp
    from app_package.routes.accounts import accounts_bp
    from app_package.routes.compose import compose_bp
    from app_package.routes.posts import posts_bp
    from app_package.routes.comments import comments_bp
    from app_package.routes.analytics import analytics_bp
    from app_package.routes.admin import admin_bp
    from app_package.routes.prospecting import prospecting_bp
    from app_package.routes.ai_insights import ai_insights_bp
    from app_package.routes.daily_tasks import daily_tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(compose_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(prospecting_bp)
    app.register_blueprint(ai_insights_bp)
    app.register_blueprint(daily_tasks_bp)

    # Create tables
    with app.app_context():
        from app_package import models  # noqa: F401
        db.create_all()

    return app
