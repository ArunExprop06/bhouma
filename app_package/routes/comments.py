from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app_package import db
from app_package.models import PostResult, Comment, SocialAccount
from app_package.services import facebook as fb_svc, instagram as ig_svc, linkedin as li_svc

comments_bp = Blueprint('comments', __name__, url_prefix='/comments')


@comments_bp.route('/')
@login_required
def inbox():
    platform_filter = request.args.get('platform', '')
    query = db.session.query(Comment).join(PostResult)
    if platform_filter:
        query = query.filter(PostResult.platform == platform_filter)
    comments = query.order_by(Comment.created_at.desc()).all()
    return render_template('comments/inbox.html', comments=comments, platform_filter=platform_filter)


@comments_bp.route('/fetch', methods=['POST'])
@login_required
def fetch_comments():
    """Fetch latest comments from all platforms for all published posts."""
    results = db.session.query(PostResult).filter_by(status='success').all()
    count = 0
    for result in results:
        account = db.session.get(SocialAccount, result.social_account_id)
        if not account or not account.is_active or not result.platform_post_id:
            continue
        try:
            if result.platform == 'facebook':
                api_comments = fb_svc.get_post_comments(result.platform_post_id, account.access_token)
                for c in api_comments:
                    existing = db.session.query(Comment).filter_by(
                        platform_comment_id=c['id']).first()
                    if not existing:
                        comment = Comment(
                            post_result_id=result.id,
                            platform_comment_id=c['id'],
                            author_name=c.get('from', {}).get('name', 'Unknown'),
                            content=c.get('message', ''),
                        )
                        db.session.add(comment)
                        count += 1

            elif result.platform == 'instagram':
                api_comments = ig_svc.get_media_comments(result.platform_post_id, account.access_token)
                for c in api_comments:
                    existing = db.session.query(Comment).filter_by(
                        platform_comment_id=c['id']).first()
                    if not existing:
                        comment = Comment(
                            post_result_id=result.id,
                            platform_comment_id=c['id'],
                            author_name=c.get('username', 'Unknown'),
                            content=c.get('text', ''),
                        )
                        db.session.add(comment)
                        count += 1

            elif result.platform == 'linkedin':
                api_comments = li_svc.get_post_comments(result.platform_post_id, account.access_token)
                for c in api_comments:
                    cid = c.get('$URN', c.get('id', ''))
                    existing = db.session.query(Comment).filter_by(
                        platform_comment_id=str(cid)).first()
                    if not existing:
                        actor = c.get('actor~', {})
                        comment = Comment(
                            post_result_id=result.id,
                            platform_comment_id=str(cid),
                            author_name=actor.get('localizedFirstName', '') + ' ' + actor.get('localizedLastName', ''),
                            content=c.get('message', {}).get('text', '') if isinstance(c.get('message'), dict) else str(c.get('message', '')),
                        )
                        db.session.add(comment)
                        count += 1

        except Exception:
            continue

    db.session.commit()
    flash(f'Fetched {count} new comment(s).', 'success')
    return redirect(url_for('comments.inbox'))


@comments_bp.route('/reply/<int:comment_id>', methods=['POST'])
@login_required
def reply(comment_id):
    comment = db.session.get(Comment, comment_id)
    if not comment:
        flash('Comment not found.', 'danger')
        return redirect(url_for('comments.inbox'))

    reply_text = request.form.get('reply', '').strip()
    if not reply_text:
        flash('Reply cannot be empty.', 'danger')
        return redirect(url_for('comments.inbox'))

    result = comment.post_result
    account = db.session.get(SocialAccount, result.social_account_id)
    if not account:
        flash('Account not found.', 'danger')
        return redirect(url_for('comments.inbox'))

    try:
        if result.platform == 'facebook':
            fb_svc.reply_to_comment(comment.platform_comment_id, account.access_token, reply_text)
        elif result.platform == 'instagram':
            ig_svc.reply_to_comment(comment.platform_comment_id, account.access_token, reply_text)
        elif result.platform == 'linkedin':
            li_svc.reply_to_comment(result.platform_post_id, account.access_token, reply_text,
                                    parent_comment=comment.platform_comment_id)

        comment.replied = True
        comment.reply_content = reply_text
        db.session.commit()
        flash('Reply sent!', 'success')
    except Exception as e:
        flash(f'Reply failed: {e}', 'danger')

    return redirect(url_for('comments.inbox'))
