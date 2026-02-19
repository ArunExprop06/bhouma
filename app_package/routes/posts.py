import io
import re
from urllib.parse import quote

import qrcode
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, current_app
from flask_login import login_required
from markupsafe import Markup
from app_package import db
from app_package.models import Post, PostResult, SocialAccount


def _post_urls(post):
    """Return (base_url, image_url, clean_text, preview_url) for a post."""
    base = current_app.config['BASE_URL'].rstrip('/')
    clean_text = re.sub(r'<[^>]+>', '', post.content).strip()
    image_url = None
    if post.image:
        fname = post.image.replace('\\', '/').split('/')[-1]
        image_url = base + url_for('uploaded_file', filename=fname)
    preview_url = base + url_for('posts.preview', post_id=post.id)
    return base, image_url, clean_text, preview_url

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
    _, image_url, clean_text, preview_url = _post_urls(post)
    return render_template('posts/detail.html', post=post, results=results,
                           preview_url=preview_url, clean_text=clean_text)


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


@posts_bp.route('/<int:post_id>/qr')
@login_required
def whatsapp_qr(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('posts.list_posts'))
    base, image_url, clean_text, _ = _post_urls(post)
    parts = ['Please approve post\n', clean_text]
    if image_url:
        parts.append(image_url)
    wa_url = 'https://wa.me/?text=' + quote('\n\n'.join(parts))
    img = qrcode.make(wa_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@posts_bp.route('/<int:post_id>/preview')
def preview(post_id):
    """Public post page with OG meta tags — used as the URL for Facebook/LinkedIn share."""
    post = db.session.get(Post, post_id)
    if not post:
        return 'Post not found', 404
    _, image_url, clean_text, preview_url = _post_urls(post)
    return render_template('posts/share.html', post=post,
                           image_url=image_url, clean_text=clean_text,
                           preview_url=preview_url)
