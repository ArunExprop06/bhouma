"""Facebook Graph API v22.0 service."""
import requests
from flask import current_app

GRAPH_URL = 'https://graph.facebook.com/v22.0'


def get_auth_url(redirect_uri):
    app_id = current_app.config['META_APP_ID']
    scopes = 'pages_show_list,pages_manage_posts,pages_read_engagement,pages_read_user_content,pages_manage_engagement,read_insights'
    return (
        f'https://www.facebook.com/v22.0/dialog/oauth'
        f'?client_id={app_id}&redirect_uri={redirect_uri}'
        f'&scope={scopes}&response_type=code'
    )


def exchange_code(code, redirect_uri):
    """Exchange authorization code for short-lived token, then get long-lived token."""
    app_id = current_app.config['META_APP_ID']
    app_secret = current_app.config['META_APP_SECRET']

    # Short-lived token
    resp = requests.get(f'{GRAPH_URL}/oauth/access_token', params={
        'client_id': app_id,
        'client_secret': app_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Token exchange failed'))
    short_token = data['access_token']

    # Long-lived token
    resp = requests.get(f'{GRAPH_URL}/oauth/access_token', params={
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': short_token,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Long-lived token failed'))
    return data['access_token']


def get_pages(user_token):
    """Get list of pages the user manages."""
    resp = requests.get(f'{GRAPH_URL}/me/accounts', params={
        'access_token': user_token,
        'fields': 'id,name,access_token,picture',
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Failed to get pages'))
    return data.get('data', [])


def get_page_info(page_id, page_token):
    """Get page info."""
    resp = requests.get(f'{GRAPH_URL}/{page_id}', params={
        'access_token': page_token,
        'fields': 'id,name,picture',
    }, timeout=15)
    return resp.json()


def publish_text(page_id, page_token, message):
    """Publish a text post to a Facebook Page."""
    resp = requests.post(f'{GRAPH_URL}/{page_id}/feed', data={
        'message': message,
        'access_token': page_token,
    }, timeout=30)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Publish failed'))
    return data.get('id')


def publish_photo(page_id, page_token, message, image_path):
    """Publish a photo post to a Facebook Page."""
    with open(image_path, 'rb') as f:
        resp = requests.post(f'{GRAPH_URL}/{page_id}/photos', data={
            'message': message,
            'access_token': page_token,
        }, files={'source': f}, timeout=60)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Photo publish failed'))
    return data.get('post_id') or data.get('id')


def get_post_comments(post_id, page_token):
    """Get comments on a post."""
    resp = requests.get(f'{GRAPH_URL}/{post_id}/comments', params={
        'access_token': page_token,
        'fields': 'id,message,from,created_time',
        'limit': 100,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Failed to get comments'))
    return data.get('data', [])


def reply_to_comment(comment_id, page_token, message):
    """Reply to a comment."""
    resp = requests.post(f'{GRAPH_URL}/{comment_id}/comments', data={
        'message': message,
        'access_token': page_token,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Reply failed'))
    return data.get('id')


def get_page_insights(page_id, page_token, period='day'):
    """Get page insights."""
    metrics = 'page_impressions,page_engaged_users,page_fans'
    resp = requests.get(f'{GRAPH_URL}/{page_id}/insights', params={
        'access_token': page_token,
        'metric': metrics,
        'period': period,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        return {}
    return data.get('data', [])


def get_post_insights(post_id, page_token):
    """Get engagement for a specific post."""
    resp = requests.get(f'{GRAPH_URL}/{post_id}', params={
        'access_token': page_token,
        'fields': 'likes.summary(true),comments.summary(true),shares',
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        return {'likes': 0, 'comments': 0, 'shares': 0}
    return {
        'likes': data.get('likes', {}).get('summary', {}).get('total_count', 0),
        'comments': data.get('comments', {}).get('summary', {}).get('total_count', 0),
        'shares': data.get('shares', {}).get('count', 0),
    }
