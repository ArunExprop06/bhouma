from flask import Blueprint, render_template, request
from flask_login import login_required
from app_package import db
from app_package.models import SocialAccount, PostResult
from app_package.services import facebook as fb_svc, instagram as ig_svc, linkedin as li_svc

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/')
@login_required
def overview():
    accounts = db.session.query(SocialAccount).filter_by(is_active=True).all()
    account_id = request.args.get('account_id', type=int)

    insights = {}
    selected_account = None

    if account_id:
        selected_account = db.session.get(SocialAccount, account_id)
        if selected_account:
            try:
                if selected_account.platform == 'facebook':
                    page_insights = fb_svc.get_page_insights(
                        selected_account.page_id, selected_account.access_token)
                    insights['raw'] = page_insights
                elif selected_account.platform == 'instagram':
                    ig_id = selected_account.get_extra('ig_user_id') or selected_account.platform_account_id
                    ig_insights = ig_svc.get_account_insights(ig_id, selected_account.access_token)
                    insights['raw'] = ig_insights
                elif selected_account.platform == 'linkedin':
                    org_id = selected_account.platform_account_id
                    followers = li_svc.get_org_followers(org_id, selected_account.access_token)
                    shares = li_svc.get_share_statistics(org_id, selected_account.access_token)
                    insights['followers'] = followers
                    insights['shares'] = shares
            except Exception:
                insights['error'] = 'Failed to fetch insights from the platform.'

    # Post-level engagement stats from DB — convert Row objects to plain lists
    raw_stats = db.session.query(
        PostResult.platform,
        db.func.sum(PostResult.likes_count),
        db.func.sum(PostResult.comments_count),
        db.func.sum(PostResult.shares_count),
        db.func.count(PostResult.id),
    ).filter_by(status='success').group_by(PostResult.platform).all()
    post_stats = [list(row) for row in raw_stats]

    return render_template('analytics/overview.html',
                           accounts=accounts,
                           selected_account=selected_account,
                           insights=insights,
                           post_stats=post_stats)
