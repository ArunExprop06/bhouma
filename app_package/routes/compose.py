import os
import uuid
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app_package import db
from app_package.models import SocialAccount, Post, PostResult
from app_package.services import facebook as fb_svc, instagram as ig_svc, linkedin as li_svc

compose_bp = Blueprint('compose', __name__, url_prefix='/compose')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@compose_bp.route('/', methods=['GET', 'POST'])
@login_required
def compose():
    accounts = db.session.query(SocialAccount).filter_by(is_active=True).all()

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        selected_accounts = request.form.getlist('accounts')
        action = request.form.get('action', 'publish')  # publish / schedule / draft
        schedule_date = request.form.get('schedule_date', '')
        schedule_time = request.form.get('schedule_time', '')

        if not content:
            flash('Post content cannot be empty.', 'danger')
            return redirect(url_for('compose.compose'))
        if action != 'draft' and not selected_accounts:
            flash('Select at least one account to publish to.', 'danger')
            return redirect(url_for('compose.compose'))

        # Handle image upload
        image_path = None
        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{uuid.uuid4().hex}.{ext}'
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)

        # Create post record
        post = Post(
            created_by=current_user.id,
            content=content,
            image=image_path,
        )
        post.set_platform_ids([int(a) for a in selected_accounts])

        if action == 'draft':
            post.status = 'draft'
            db.session.add(post)
            db.session.commit()
            flash('Post saved as draft.', 'info')
            return redirect(url_for('posts.list_posts'))

        if action == 'schedule':
            if schedule_date and schedule_time:
                scheduled_at = datetime.strptime(f'{schedule_date} {schedule_time}', '%Y-%m-%d %H:%M')
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
                post.scheduled_at = scheduled_at
                post.status = 'scheduled'
                db.session.add(post)
                db.session.commit()
                flash(f'Post scheduled for {scheduled_at.strftime("%b %d, %Y %H:%M")} UTC.', 'success')
                return redirect(url_for('posts.list_posts'))
            else:
                flash('Please select a date and time for scheduling.', 'danger')
                return redirect(url_for('compose.compose'))

        # Publish now
        post.status = 'publishing'
        db.session.add(post)
        db.session.commit()

        publish_post(post)
        return redirect(url_for('posts.detail', post_id=post.id))

    return render_template('compose/compose.html', accounts=accounts)


def publish_post(post):
    """Publish a post to all selected platforms."""
    account_ids = post.get_platform_ids()
    any_success = False

    for acc_id in account_ids:
        account = db.session.get(SocialAccount, acc_id)
        if not account or not account.is_active:
            continue

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
                    # IG requires a public image URL; for local dev use the BASE_URL
                    image_url = current_app.config['BASE_URL'] + '/uploads/' + os.path.basename(post.image)
                    ig_user_id = account.get_extra('ig_user_id') or account.platform_account_id
                    platform_post_id = ig_svc.publish_photo(
                        ig_user_id, account.access_token, image_url, post.content)
                else:
                    result.status = 'failed'
                    result.error_message = 'Instagram requires an image to publish.'
                    db.session.add(result)
                    continue

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
            any_success = True

        except Exception as e:
            result.status = 'failed'
            result.error_message = str(e)

        db.session.add(result)

    post.status = 'published' if any_success else 'failed'
    post.published_at = datetime.now(timezone.utc) if any_success else None
    db.session.commit()

    if any_success:
        flash('Post published successfully!', 'success')
    else:
        flash('Post publishing failed on all platforms.', 'danger')
