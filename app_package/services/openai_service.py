import json
from flask import current_app


def _get_client():
    """Lazy-import openai to avoid startup crash if key is missing."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError('openai package is not installed. Run: pip install openai>=1.30')

    api_key = current_app.config.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured.')

    return OpenAI(api_key=api_key)


def generate_insights(account_name, platform, score_data, metrics):
    """Generate AI insights for a connected social account."""
    client = _get_client()

    top_snippets = '\n'.join(
        f"- \"{p['snippet']}\" (likes:{p['likes']}, comments:{p['comments']}, shares:{p['shares']})"
        for p in metrics.get('top_posts', [])
    ) or 'No top posts available.'

    weak_snippets = '\n'.join(
        f"- \"{p['snippet']}\" (likes:{p['likes']}, comments:{p['comments']}, shares:{p['shares']})"
        for p in metrics.get('weak_posts', [])
    ) or 'No weak posts available.'

    prompt = f"""You are a social media strategist. Analyze this {platform} account and provide actionable insights.

Account: {account_name}
Platform: {platform}
Health Score: {score_data['total']}/100 ({score_data['label']})

Score Breakdown:
- Engagement: {score_data['dimensions']['engagement']}/25
- Consistency: {score_data['dimensions']['consistency']}/25
- Quality: {score_data['dimensions']['quality']}/25
- Growth: {score_data['dimensions']['growth']}/25

30-Day Metrics:
- Total Posts: {metrics['total_posts_30d']}
- Posts Per Week: {metrics['posts_per_week']}
- Total Engagement: {metrics['total_engagement_30d']} (Likes: {metrics['likes_30d']}, Comments: {metrics['comments_30d']}, Shares: {metrics['shares_30d']})
- Engagement Per Post: {metrics['engagement_per_post']}
- Comment-to-Like Ratio: {metrics['quality_ratio']}

Top Performing Posts (30d):
{top_snippets}

Weakest Posts (30d):
{weak_snippets}

Respond in JSON with these exact keys:
- "summary": 2-3 sentence overview of account health
- "what_is_working": array of 2-3 things going well
- "needs_improvement": array of 2-3 areas to improve
- "action_items": array of 3-5 specific, actionable next steps"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.7,
            max_tokens=800,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            'summary': f'Unable to generate insights: {str(e)}',
            'what_is_working': [],
            'needs_improvement': [],
            'action_items': [],
        }


def analyze_page_url(url, platform, user_metrics):
    """Analyze any social media page URL with GPT."""
    client = _get_client()

    metrics_text = ''
    if user_metrics:
        parts = []
        if user_metrics.get('followers'):
            parts.append(f"Followers: {user_metrics['followers']}")
        if user_metrics.get('avg_likes'):
            parts.append(f"Average Likes per Post: {user_metrics['avg_likes']}")
        if user_metrics.get('avg_comments'):
            parts.append(f"Average Comments per Post: {user_metrics['avg_comments']}")
        if user_metrics.get('posts_per_week'):
            parts.append(f"Posts per Week: {user_metrics['posts_per_week']}")
        metrics_text = '\n'.join(parts)

    prompt = f"""You are a social media strategist. Analyze this {platform} page and provide a health assessment.

Page URL: {url}
Platform: {platform}
{('User-Provided Metrics:\n' + metrics_text) if metrics_text else 'No specific metrics provided - give general platform-specific advice based on best practices.'}

Rate this page from 0-100 based on the information available. If limited data is provided, assess based on platform best practices and common benchmarks for {platform}.

Respond in JSON with these exact keys:
- "score": integer 0-100
- "summary": 2-3 sentence assessment of the page
- "what_is_working": array of 2-3 positive observations or assumptions based on available data
- "needs_improvement": array of 2-3 areas that likely need attention
- "action_items": array of 3-5 specific, actionable recommendations for this {platform} page"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0.7,
            max_tokens=800,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            'score': 0,
            'summary': f'Unable to analyze page: {str(e)}',
            'what_is_working': [],
            'needs_improvement': [],
            'action_items': [],
        }
