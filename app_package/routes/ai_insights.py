import re
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app_package import db
from app_package.models import SocialAccount
from app_package.services.insights_engine import (
    compute_account_metrics,
    compute_health_score,
    get_performance_trend,
    get_all_account_health,
)

ai_insights_bp = Blueprint('ai_insights', __name__, url_prefix='/ai-insights')


@ai_insights_bp.route('/')
@login_required
def index():
    accounts = (
        db.session.query(SocialAccount)
        .filter_by(user_id=current_user.id, is_active=True)
        .all()
    )

    # Compute health scores for all accounts
    account_health = get_all_account_health(accounts)

    # Trend for first account (or selected)
    selected_id = request.args.get('account_id', type=int)
    if not selected_id and accounts:
        selected_id = accounts[0].id

    trend = get_performance_trend(selected_id) if selected_id else []

    has_api_key = bool(current_app.config.get('OPENAI_API_KEY', ''))

    return render_template(
        'ai_insights/index.html',
        account_health=account_health,
        accounts=accounts,
        selected_id=selected_id,
        trend=trend,
        has_api_key=has_api_key,
    )


@ai_insights_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id')

    if not account_id:
        return jsonify({'error': 'account_id is required'}), 400

    account = db.session.get(SocialAccount, account_id)
    if not account or account.user_id != current_user.id:
        return jsonify({'error': 'Account not found'}), 404

    if not current_app.config.get('OPENAI_API_KEY'):
        return jsonify({'error': 'OPENAI_API_KEY is not configured'}), 400

    from app_package.services.openai_service import generate_insights

    metrics = compute_account_metrics(account.id)
    score = compute_health_score(metrics)
    result = generate_insights(account.account_name, account.platform, score, metrics)

    return jsonify(result)


@ai_insights_bp.route('/analyze-url', methods=['POST'])
@login_required
def analyze_url():
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not current_app.config.get('OPENAI_API_KEY'):
        return jsonify({'error': 'OPENAI_API_KEY is not configured'}), 400

    # Auto-detect platform from URL
    platform = data.get('platform', '')
    if not platform:
        lower = url.lower()
        if 'facebook.com' in lower or 'fb.com' in lower:
            platform = 'Facebook'
        elif 'linkedin.com' in lower:
            platform = 'LinkedIn'
        elif 'instagram.com' in lower:
            platform = 'Instagram'
        else:
            platform = 'Social Media'

    user_metrics = {
        'followers': data.get('followers'),
        'avg_likes': data.get('avg_likes'),
        'avg_comments': data.get('avg_comments'),
        'posts_per_week': data.get('posts_per_week'),
    }
    # Remove empty values
    user_metrics = {k: v for k, v in user_metrics.items() if v}

    from app_package.services.openai_service import analyze_page_url

    result = analyze_page_url(url, platform, user_metrics)

    return jsonify(result)


@ai_insights_bp.route('/trend', methods=['GET'])
@login_required
def trend():
    account_id = request.args.get('account_id', type=int)
    if not account_id:
        return jsonify([])

    account = db.session.get(SocialAccount, account_id)
    if not account or account.user_id != current_user.id:
        return jsonify([])

    data = get_performance_trend(account_id)
    return jsonify(data)
