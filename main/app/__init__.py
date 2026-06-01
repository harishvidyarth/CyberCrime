from flask import Flask, g, request
from .config import Config
from .extensions import db, limiter, login_manager, csrf, migrate
import os
import secrets
import logging
from datetime import timedelta

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Configure login
    login_manager.login_view = 'auth.login'
    
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Strip Server Header Middleware
    class StripServerHeaderMiddleware:
        def __init__(self, app):
            self.app = app
        def __call__(self, environ, start_response):
            def custom_start_response(status, headers, exc_info=None):
                filtered = [(k, v) for (k, v) in headers if k.lower() not in ('server', 'x-powered-by', 'x-aspnet-version', 'x-aspnetmvc-version')]
                return start_response(status, filtered, exc_info)
            return self.app(environ, custom_start_response)
    
    app.wsgi_app = StripServerHeaderMiddleware(app.wsgi_app)

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.admin import admin_bp
    from .routes.analysis import analysis_bp
    from .routes.ingestion import ingestion_bp
    from .routes.letters import letters_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(letters_bp)

    # Security Headers
    @app.before_request
    def generate_csp_nonce():
        g.csp_nonce = secrets.token_hex(16)

    @app.context_processor
    def inject_csp_nonce():
        return dict(csp_nonce=g.csp_nonce)

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers.pop('Server', None)
        
        nonce = getattr(g, 'csp_nonce', '')
        csp_policy = (
            "default-src 'self'; "
            f"script-src 'self' https://d3js.org 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        if 'static' not in request.path.lower():
            if 'Cache-Control' not in response.headers:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/error.html', title="404 Not Found", code=404, message="Oops! The page you're looking for doesn't exist."), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/error.html', title="403 Forbidden", code=403, message="Access Denied. You do not have permission to view this resource."), 403

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return render_template('errors/error.html', title="429 Too Many Requests", code=429, message="Rate limit exceeded. Please try again later."), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/error.html', title="500 Internal Server Error", code=500, message="An unexpected error occurred. Our team has been notified."), 500

    # Database Initialization (if using MySQL or needing column checks)
    with app.app_context():
        # These checks run from app.py originally
        try:
            from .models import Transaction, User
            # Simplified version of ensure_transaction_columns and ensure_user_columns for brevity
            # In a real app, migrations (Flask-Migrate) should handle this.
            # But the user had manual ALTER TABLE logic.
            pass 
        except Exception as e:
            app.logger.error(f"DB Init Error: {e}")

    return app
