from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app_package import db, login_manager
import json


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')  # admin / member
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    social_accounts = db.relationship('SocialAccount', backref='user', lazy=True)
    posts = db.relationship('Post', backref='creator', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class SocialAccount(db.Model):
    __tablename__ = 'social_accounts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    platform = db.Column(db.String(20), nullable=False)  # facebook / instagram / linkedin
    platform_account_id = db.Column(db.String(200))
    account_name = db.Column(db.String(200))
    account_image_url = db.Column(db.String(500))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    page_id = db.Column(db.String(200))
    extra_data = db.Column(db.Text)  # JSON
    is_active = db.Column(db.Boolean, default=True)
    connected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    post_results = db.relationship('PostResult', backref='social_account', lazy=True)

    def get_extra(self, key=None):
        data = json.loads(self.extra_data) if self.extra_data else {}
        return data.get(key) if key else data

    def set_extra(self, key, value):
        data = json.loads(self.extra_data) if self.extra_data else {}
        data[key] = value
        self.extra_data = json.dumps(data)

    @property
    def platform_icon(self):
        icons = {
            'facebook': 'bi-facebook',
            'instagram': 'bi-instagram',
            'linkedin': 'bi-linkedin',
        }
        return icons.get(self.platform, 'bi-globe')

    @property
    def platform_color(self):
        colors = {
            'facebook': '#1877f2',
            'instagram': '#e4405f',
            'linkedin': '#0a66c2',
        }
        return colors.get(self.platform, '#6c757d')


class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text)
    image = db.Column(db.String(300))  # uploaded file path
    platforms = db.Column(db.Text)  # JSON list of social_account IDs
    status = db.Column(db.String(20), default='draft')  # draft/scheduled/publishing/published/failed
    scheduled_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    results = db.relationship('PostResult', backref='post', lazy=True, cascade='all, delete-orphan')

    def get_platform_ids(self):
        return json.loads(self.platforms) if self.platforms else []

    def set_platform_ids(self, ids):
        self.platforms = json.dumps(ids)

    @property
    def status_color(self):
        colors = {
            'published': 'success',
            'scheduled': 'warning',
            'draft': 'secondary',
            'publishing': 'info',
            'failed': 'danger',
        }
        return colors.get(self.status, 'secondary')


class PostResult(db.Model):
    __tablename__ = 'post_results'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    social_account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id'), nullable=False)
    platform = db.Column(db.String(20))
    platform_post_id = db.Column(db.String(300))
    status = db.Column(db.String(20), default='pending')  # success / failed
    error_message = db.Column(db.Text)
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime)

    comments = db.relationship('Comment', backref='post_result', lazy=True, cascade='all, delete-orphan')


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    post_result_id = db.Column(db.Integer, db.ForeignKey('post_results.id'), nullable=False)
    platform_comment_id = db.Column(db.String(300))
    author_name = db.Column(db.String(200))
    author_image = db.Column(db.String(500))
    content = db.Column(db.Text)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    replied = db.Column(db.Boolean, default=False)
    reply_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side='Comment.id'), lazy=True)


class TaskTemplate(db.Model):
    __tablename__ = 'task_templates'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    platform = db.Column(db.String(20), default='general')  # facebook/instagram/linkedin/general
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    instances = db.relationship('DailyTaskInstance', backref='template', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('TaskAssignment', backref='template', lazy=True, cascade='all, delete-orphan')

    @property
    def assigned_user_ids(self):
        return [a.user_id for a in self.assignments]

    @property
    def platform_icon(self):
        icons = {
            'facebook': 'bi-facebook',
            'instagram': 'bi-instagram',
            'linkedin': 'bi-linkedin',
            'general': 'bi-check2-circle',
        }
        return icons.get(self.platform, 'bi-check2-circle')

    @property
    def platform_color(self):
        colors = {
            'facebook': '#1877f2',
            'instagram': '#e4405f',
            'linkedin': '#0a66c2',
            'general': '#6c757d',
        }
        return colors.get(self.platform, '#6c757d')


class DailyTaskInstance(db.Model):
    __tablename__ = 'daily_task_instances'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('task_templates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_date = db.Column(db.Date, nullable=False, default=date.today)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='task_instances')

    __table_args__ = (
        db.UniqueConstraint('template_id', 'user_id', 'task_date', name='uq_task_user_date'),
    )


class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('task_templates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='task_assignments')

    __table_args__ = (
        db.UniqueConstraint('template_id', 'user_id', name='uq_assignment_template_user'),
    )


class AppSetting(db.Model):
    __tablename__ = 'app_settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        row = db.session.get(AppSetting, key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = db.session.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.session.add(AppSetting(key=key, value=value))
        db.session.commit()
