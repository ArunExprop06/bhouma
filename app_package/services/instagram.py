"""Instagram Graph API v22.0 service (via Meta Business)."""
import requests
import time
from flask import current_app

GRAPH_URL = 'https://graph.facebook.com/v22.0'


def get_auth_url(redirect_uri):
    """Instagram uses the same Meta OAuth as Facebook, with IG-specific scopes."""
    app_id = current_app.config['META_APP_ID']
    scopes = (
        'pages_show_list,instagram_basic,instagram_content_publish,'
        'instagram_manage_comments,instagram_manage_insights'
    )
    return (
        f'https://www.facebook.com/v22.0/dialog/oauth'
        f'?client_id={app_id}&redirect_uri={redirect_uri}'
        f'&scope={scopes}&response_type=code'
    )


def get_ig_account_from_page(page_id, page_token):
    """Get the Instagram Business Account linked to a Facebook Page."""
    resp = requests.get(f'{GRAPH_URL}/{page_id}', params={
        'access_token': page_token,
        'fields': 'instagram_business_account',
    }, timeout=15)
    data = resp.json()
    ig_account = data.get('instagram_business_account')
    if not ig_account:
        return None
    return ig_account.get('id')


def get_ig_profile(ig_user_id, token):
    """Get IG business profile info."""
    resp = requests.get(f'{GRAPH_URL}/{ig_user_id}', params={
        'access_token': token,
        'fields': 'id,name,username,profile_picture_url,followers_count,media_count',
    }, timeout=15)
    return resp.json()


def publish_photo(ig_user_id, token, image_url, caption=''):
    """Two-step publish: create container, then publish."""
    # Step 1: Create container
    resp = requests.post(f'{GRAPH_URL}/{ig_user_id}/media', data={
        'image_url': image_url,
        'caption': caption,
        'access_token': token,
    }, timeout=30)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Container creation failed'))
    container_id = data['id']

    # Wait for container to be ready
    time.sleep(3)

    # Step 2: Publish
    resp = requests.post(f'{GRAPH_URL}/{ig_user_id}/media_publish', data={
        'creation_id': container_id,
        'access_token': token,
    }, timeout=30)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Publish failed'))
    return data.get('id')


def get_media_comments(media_id, token):
    """Get comments on an IG media."""
    resp = requests.get(f'{GRAPH_URL}/{media_id}/comments', params={
        'access_token': token,
        'fields': 'id,text,username,timestamp',
        'limit': 100,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Failed to get comments'))
    return data.get('data', [])


def reply_to_comment(comment_id, token, message):
    """Reply to an IG comment."""
    resp = requests.post(f'{GRAPH_URL}/{comment_id}/replies', data={
        'message': message,
        'access_token': token,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data['error'].get('message', 'Reply failed'))
    return data.get('id')


def get_account_insights(ig_user_id, token, period='day'):
    """Get IG account insights."""
    metrics = 'impressions,reach,follower_count'
    resp = requests.get(f'{GRAPH_URL}/{ig_user_id}/insights', params={
        'access_token': token,
        'metric': metrics,
        'period': period,
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        return []
    return data.get('data', [])


def get_media_insights(media_id, token):
    """Get insights for a specific IG media."""
    resp = requests.get(f'{GRAPH_URL}/{media_id}/insights', params={
        'access_token': token,
        'metric': 'impressions,reach,engagement',
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        return {}
    result = {}
    for item in data.get('data', []):
        result[item['name']] = item['values'][0]['value'] if item.get('values') else 0
    return result
