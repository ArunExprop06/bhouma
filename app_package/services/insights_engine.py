from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from app_package import db
from app_package.models import PostResult, Post, SocialAccount


def compute_account_metrics(account_id):
    """Compute engagement metrics for a social account from DB data (no API calls)."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    # Posts in 30d and 90d
    posts_30d = (
        db.session.query(PostResult)
        .filter(
            PostResult.social_account_id == account_id,
            PostResult.status == 'success',
            PostResult.published_at >= thirty_days_ago,
        )
        .all()
    )
    posts_90d = (
        db.session.query(PostResult)
        .filter(
            PostResult.social_account_id == account_id,
            PostResult.status == 'success',
            PostResult.published_at >= ninety_days_ago,
        )
        .all()
    )

    total_30d = len(posts_30d)
    total_90d = len(posts_90d)

    # Engagement sums for 30d
    likes_30d = sum(p.likes_count or 0 for p in posts_30d)
    comments_30d = sum(p.comments_count or 0 for p in posts_30d)
    shares_30d = sum(p.shares_count or 0 for p in posts_30d)
    total_engagement_30d = likes_30d + comments_30d + shares_30d

    # Derived metrics
    posts_per_week = round(total_30d / 4.3, 1) if total_30d else 0
    engagement_per_post = round(total_engagement_30d / total_30d, 1) if total_30d else 0
    quality_ratio = round(comments_30d / likes_30d, 4) if likes_30d else 0

    # Historical max engagement per post (90d) for normalization
    if total_90d:
        engagements_90d = [
            (p.likes_count or 0) + (p.comments_count or 0) + (p.shares_count or 0)
            for p in posts_90d
        ]
        historical_max = max(engagements_90d) if engagements_90d else 1
    else:
        historical_max = 1

    # Top and weakest posts (by engagement, 30d)
    ranked = sorted(
        posts_30d,
        key=lambda p: (p.likes_count or 0) + (p.comments_count or 0) + (p.shares_count or 0),
        reverse=True,
    )
    top_posts = []
    weak_posts = []
    for pr in ranked[:3]:
        post = db.session.get(Post, pr.post_id)
        snippet = (post.content or '')[:120] if post else ''
        eng = (pr.likes_count or 0) + (pr.comments_count or 0) + (pr.shares_count or 0)
        top_posts.append({'snippet': snippet, 'engagement': eng, 'likes': pr.likes_count or 0,
                          'comments': pr.comments_count or 0, 'shares': pr.shares_count or 0})
    for pr in ranked[-3:] if len(ranked) > 3 else ranked:
        post = db.session.get(Post, pr.post_id)
        snippet = (post.content or '')[:120] if post else ''
        eng = (pr.likes_count or 0) + (pr.comments_count or 0) + (pr.shares_count or 0)
        weak_posts.append({'snippet': snippet, 'engagement': eng, 'likes': pr.likes_count or 0,
                           'comments': pr.comments_count or 0, 'shares': pr.shares_count or 0})

    return {
        'total_posts_30d': total_30d,
        'total_posts_90d': total_90d,
        'likes_30d': likes_30d,
        'comments_30d': comments_30d,
        'shares_30d': shares_30d,
        'total_engagement_30d': total_engagement_30d,
        'posts_per_week': posts_per_week,
        'engagement_per_post': engagement_per_post,
        'quality_ratio': quality_ratio,
        'historical_max': historical_max,
        'top_posts': top_posts,
        'weak_posts': weak_posts,
    }


def compute_health_score(metrics):
    """Compute a 0-100 health score from metrics with 4 dimensions (0-25 each)."""
    # Engagement score (0-25): engagement_per_post / historical_max
    if metrics['historical_max'] > 0:
        engagement_raw = metrics['engagement_per_post'] / metrics['historical_max']
    else:
        engagement_raw = 0
    engagement_score = min(round(engagement_raw * 25), 25)

    # Consistency score (0-25): posts_per_week / 7
    consistency_raw = metrics['posts_per_week'] / 7
    consistency_score = min(round(consistency_raw * 25), 25)

    # Quality score (0-25): quality_ratio / 0.05
    quality_raw = metrics['quality_ratio'] / 0.05 if metrics['quality_ratio'] else 0
    quality_score = min(round(quality_raw * 25), 25)

    # Growth score (0-25): based on engagement trend
    if metrics['total_posts_90d'] > 0 and metrics['total_posts_30d'] > 0:
        avg_eng_90d = metrics.get('total_engagement_30d', 0) / max(metrics['total_posts_30d'], 1)
        growth_raw = min(avg_eng_90d / max(metrics['historical_max'], 1), 1)
    else:
        growth_raw = 0
    growth_score = min(round(growth_raw * 25), 25)

    total = engagement_score + consistency_score + quality_score + growth_score

    if total >= 80:
        label = 'Excellent'
        color = '#198754'
    elif total >= 60:
        label = 'Good'
        color = '#4361ee'
    elif total >= 40:
        label = 'Average'
        color = '#ffc107'
    elif total >= 20:
        label = 'Needs Work'
        color = '#fd7e14'
    else:
        label = 'Poor'
        color = '#dc3545'

    return {
        'total': total,
        'label': label,
        'color': color,
        'dimensions': {
            'engagement': engagement_score,
            'consistency': consistency_score,
            'quality': quality_score,
            'growth': growth_score,
        },
    }


def get_performance_trend(account_id, weeks=8):
    """Get weekly engagement + post count for trend chart."""
    now = datetime.now(timezone.utc)
    trend = []

    for i in range(weeks - 1, -1, -1):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        results = (
            db.session.query(PostResult)
            .filter(
                PostResult.social_account_id == account_id,
                PostResult.status == 'success',
                PostResult.published_at >= week_start,
                PostResult.published_at < week_end,
            )
            .all()
        )

        post_count = len(results)
        engagement = sum(
            (r.likes_count or 0) + (r.comments_count or 0) + (r.shares_count or 0)
            for r in results
        )

        trend.append({
            'week': week_start.strftime('%b %d'),
            'posts': post_count,
            'engagement': engagement,
        })

    return trend


def get_all_account_health(accounts):
    """Compute health scores for a list of social accounts."""
    results = []
    for account in accounts:
        metrics = compute_account_metrics(account.id)
        score = compute_health_score(metrics)
        results.append({
            'account': account,
            'metrics': metrics,
            'score': score,
        })
    return results
