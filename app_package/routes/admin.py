from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app_package import db
from app_package.models import User, SocialAccount
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = db.session.query(User).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/invite', methods=['POST'])
@login_required
@admin_required
def invite_user():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'member')

    if not name or not email or not password:
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))

    if db.session.query(User).filter_by(email=email).first():
        flash('Email already registered.', 'danger')
        return redirect(url_for('admin.users'))

    user = User(name=name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'Team member {name} invited!', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user.is_active_user = not user.is_active_user
        db.session.commit()
        status = 'activated' if user.is_active_user else 'deactivated'
        flash(f'User {user.name} {status}.', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    accounts = db.session.query(SocialAccount).all()
    return render_template('admin/settings.html', accounts=accounts)
