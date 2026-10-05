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


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
