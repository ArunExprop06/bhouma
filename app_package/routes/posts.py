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
    # Connected pages for "share to page" buttons
    accounts = db.session.query(SocialAccount).filter_by(is_active=True).all()
    # Find which accounts already have a result for this post
    published_acc_ids = {r.social_account_id for r in results}
    return render_template('posts/detail.html', post=post, results=results,
                           preview_url=preview_url, clean_text=clean_text,
                           accounts=accounts, published_acc_ids=published_acc_ids)


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


@posts_bp.route('/<int:post_id>/share-to/<int:account_id>', methods=['POST'])
@login_required
def share_to_account(post_id, account_id):
    """Publish this post to a single connected page via API."""
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('posts.list_posts'))
    account = db.session.get(SocialAccount, account_id)
    if not account or not account.is_active:
        flash('Account not found or inactive.', 'danger')
        return redirect(url_for('posts.detail', post_id=post.id))

    from app_package.routes.compose import publish_post
    import os
    from datetime import datetime, timezone
    from app_package.services import facebook as fb_svc, instagram as ig_svc, linkedin as li_svc

    result = PostResult(
        post_id=post.id,
        social_account_id=account.id,
        platform=account.platform,
    )
    try:
        platform_post_id = None
        if account.platform == 'facebook':
            if post.image:
                platform_post_id = fb_svc.publish_photo(
                    account.page_id, account.access_token, post.content, post.image)
            else:
                platform_post_id = fb_svc.publish_text(
                    account.page_id, account.access_token, post.content)
        elif account.platform == 'instagram':
            if post.image:
                image_url = current_app.config['BASE_URL'] + '/uploads/' + os.path.basename(post.image)
                ig_user_id = account.get_extra('ig_user_id') or account.platform_account_id
                platform_post_id = ig_svc.publish_photo(
                    ig_user_id, account.access_token, image_url, post.content)
            else:
                flash('Instagram requires an image to publish.', 'danger')
                return redirect(url_for('posts.detail', post_id=post.id))
        elif account.platform == 'linkedin':
            org_urn = account.get_extra('org_urn') or f'urn:li:person:{account.platform_account_id}'
            if post.image:
                platform_post_id = li_svc.publish_image(
                    org_urn, account.access_token, post.content, post.image)
            else:
                platform_post_id = li_svc.publish_text(
                    org_urn, account.access_token, post.content)

        result.platform_post_id = platform_post_id
        result.status = 'success'
        result.published_at = datetime.now(timezone.utc)
        flash(f'Published to {account.account_name}!', 'success')
    except Exception as e:
        result.status = 'failed'
        result.error_message = str(e)
        flash(f'Failed to publish to {account.account_name}: {e}', 'danger')

    db.session.add(result)
    if post.status == 'draft':
        post.status = 'published'
        post.published_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for('posts.detail', post_id=post.id))


@posts_bp.route('/<int:post_id>/qr')
@login_required
def whatsapp_qr(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('posts.list_posts'))
    base = current_app.config['BASE_URL'].rstrip('/')
    share_url = base + url_for('posts.whatsapp_share', post_id=post.id)
    img = qrcode.make(share_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@posts_bp.route('/<int:post_id>/whatsapp')
def whatsapp_share(post_id):
    """Public page opened after QR scan — shares image + text to WhatsApp via Web Share API."""
    post = db.session.get(Post, post_id)
    if not post:
        return 'Post not found', 404
    _, image_url, clean_text, _ = _post_urls(post)
    return render_template('posts/whatsapp_share.html',
                           post=post, image_url=image_url, clean_text=clean_text)


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
