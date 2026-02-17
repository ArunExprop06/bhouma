from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app_package import db
from app_package.models import Post, PostResult, SocialAccount

posts_bp = Blueprint('posts', __name__, url_prefix='/posts')


@posts_bp.route('/')
@login_required
def list_posts():
    posts = db.session.query(Post).order_by(Post.created_at.desc()).all()
    return render_template('posts/list.html', posts=posts)


@posts_bp.route('/<int:post_id>')
@login_required
def detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('posts.list_posts'))
    results = db.session.query(PostResult).filter_by(post_id=post.id).all()
    return render_template('posts/detail.html', post=post, results=results)


@posts_bp.route('/<int:post_id>/republish', methods=['POST'])
@login_required
def republish(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('posts.list_posts'))
    # Remove old failed results
    for r in post.results:
        if r.status == 'failed':
            db.session.delete(r)
    db.session.commit()

    from app_package.routes.compose import publish_post
    post.status = 'publishing'
    db.session.commit()
    publish_post(post)
    return redirect(url_for('posts.detail', post_id=post.id))
