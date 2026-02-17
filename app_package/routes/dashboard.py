from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app_package import db
from app_package.models import SocialAccount, Post, Comment
from datetime import datetime, timezone, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    accounts = db.session.query(SocialAccount).filter_by(is_active=True).all()
    recent_posts = db.session.query(Post).order_by(Post.created_at.desc()).limit(10).all()

    # Stats for this week
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    posts_this_week = db.session.query(Post).filter(Post.created_at >= week_ago).count()
    total_comments = db.session.query(Comment).count()
    published_posts = db.session.query(Post).filter_by(status='published').count()
    scheduled_posts = db.session.query(Post).filter_by(status='scheduled').count()

    return render_template('dashboard.html',
                           accounts=accounts,
                           recent_posts=recent_posts,
                           posts_this_week=posts_this_week,
                           total_comments=total_comments,
                           published_posts=published_posts,
                           scheduled_posts=scheduled_posts)
