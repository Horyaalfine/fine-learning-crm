from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import User, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()

        if user and user.active and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))

        flash("Incorrect email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/users")
@login_required
def users():
    if not current_user.is_admin:
        flash("Only admins can manage staff accounts.", "error")
        return redirect(url_for("dashboard.index"))
    all_users = User.query.order_by(User.name).all()
    return render_template("users.html", users=all_users)


@auth_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def new_user():
    if not current_user.is_admin:
        flash("Only admins can manage staff accounts.", "error")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        role = request.form.get("role") or "staff"

        if not name or not email or not password:
            flash("Name, email and password are all required.", "error")
            return render_template("user_form.html")

        if User.query.filter_by(email=email).first():
            flash("A user with that email already exists.", "error")
            return render_template("user_form.html")

        user = User(name=name, email=email, role=role if role in ("admin", "staff") else "staff")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"{name} added.", "success")
        return redirect(url_for("auth.users"))

    return render_template("user_form.html")
