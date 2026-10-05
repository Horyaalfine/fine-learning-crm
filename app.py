import os

import click
from flask import Flask
from flask_login import LoginManager

from config import Config
from models import User, db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from api import api_bp
    from auth import auth_bp
    from campaigns import campaigns_bp
    from dashboard import dashboard_bp
    from leads import leads_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
        _bootstrap_admin_if_needed()

    @app.cli.command("create-admin")
    @click.argument("name")
    @click.argument("email")
    @click.argument("password")
    def create_admin(name, email, password):
        """Create (or promote) an admin user: flask create-admin "Name" email pass"""
        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.role = "admin"
            user.set_password(password)
            click.echo(f"Updated existing user {email} to admin.")
        else:
            user = User(name=name, email=email, role="admin")
            user.set_password(password)
            db.session.add(user)
            click.echo(f"Created admin user {email}.")
        db.session.commit()

    return app


def _bootstrap_admin_if_needed():
    """Create the first admin account from env vars, but only while the
    users table is empty. This runs on every boot but is a no-op once any
    user exists, so leaving the env vars set afterwards is harmless - it's
    worth removing ADMIN_BOOTSTRAP_PASSWORD from Railway once logged in,
    simply to stop it sitting in the variable list."""
    if User.query.count() > 0:
        return

    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    name = os.environ.get("ADMIN_BOOTSTRAP_NAME", "Admin")

    if not email or not password:
        return

    admin = User(name=name, email=email, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
