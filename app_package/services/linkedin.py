"""LinkedIn REST API service."""
import requests
from urllib.parse import quote
from flask import current_app

API_URL = 'https://api.linkedin.com'


def get_auth_url(redirect_uri, state=''):
    client_id = current_app.config['LINKEDIN_CLIENT_ID']
    scopes = 'openid profile email w_member_social'
    return (
        f'https://www.linkedin.com/oauth/v2/authorization'
        f'?response_type=code&client_id={client_id}'
        f'&redirect_uri={quote(redirect_uri, safe="")}&scope={quote(scopes)}'
        f'&state={state}'
    )


def exchange_code(code, redirect_uri):
    """Exchange authorization code for access token."""
    resp = requests.post('https://www.linkedin.com/oauth/v2/accessToken', data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': current_app.config['LINKEDIN_CLIENT_ID'],
        'client_secret': current_app.config['LINKEDIN_CLIENT_SECRET'],
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data.get('error_description', 'Token exchange failed'))
    return {
        'access_token': data['access_token'],
        'expires_in': data.get('expires_in', 5184000),
        'refresh_token': data.get('refresh_token', ''),
        'refresh_token_expires_in': data.get('refresh_token_expires_in', 0),
    }


def refresh_access_token(refresh_token):
    """Refresh a LinkedIn access token."""
    resp = requests.post('https://www.linkedin.com/oauth/v2/accessToken', data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': current_app.config['LINKEDIN_CLIENT_ID'],
        'client_secret': current_app.config['LINKEDIN_CLIENT_SECRET'],
    }, timeout=15)
    data = resp.json()
    if 'error' in data:
        raise Exception(data.get('error_description', 'Token refresh failed'))
    return data


def _headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
        'LinkedIn-Version': '202405',
    }


def get_user_profile(token):
    """Get the authenticated user's LinkedIn profile."""
    resp = requests.get(
        f'{API_URL}/v2/userinfo',
        headers={'Authorization': f'Bearer {token}'},
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return {
        'id': data.get('sub', ''),
        'name': data.get('name', ''),
        'logo_url': data.get('picture', ''),
        'urn': f'urn:li:person:{data.get("sub", "")}',
    }


def get_organization_pages(token):
    """Get organization pages the user administers."""
    resp = requests.get(
        f'{API_URL}/rest/organizationAcls',
        params={'q': 'roleAssignee', 'role': 'ADMINISTRATOR', 'state': 'APPROVED'},
        headers=_headers(token),
        timeout=15,
    )
    data = resp.json()
    orgs = []
    for item in data.get('elements', []):
        org_urn = item.get('organization')
        if org_urn:
            org_id = org_urn.split(':')[-1]
            org_info = get_organization_info(org_id, token)
            if org_info:
                orgs.append(org_info)
    return orgs


def get_organization_info(org_id, token):
    """Get organization details."""
    resp = requests.get(
        f'{API_URL}/rest/organizations/{org_id}',
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    logo_url = ''
    logo = data.get('logoV2', {}).get('original~', {}).get('elements', [])
    if logo:
        logo_url = logo[0].get('identifiers', [{}])[0].get('identifier', '')
    return {
        'id': org_id,
        'name': data.get('localizedName', ''),
        'logo_url': logo_url,
        'urn': f'urn:li:organization:{org_id}',
    }


def publish_text(org_urn, token, text):
    """Publish a text post on behalf of an organization."""
    payload = {
        'author': org_urn,
        'commentary': text,
        'visibility': 'PUBLIC',
        'distribution': {
            'feedDistribution': 'MAIN_FEED',
            'targetEntities': [],
            'thirdPartyDistributionChannels': [],
        },
        'lifecycleState': 'PUBLISHED',
    }
    resp = requests.post(
        f'{API_URL}/rest/posts',
        json=payload,
        headers=_headers(token),
        timeout=30,
    )
    if resp.status_code in (200, 201):
        post_header = resp.headers.get('x-restli-id', '')
        return post_header or resp.json().get('id', '')
    data = resp.json() if resp.content else {}
    raise Exception(data.get('message', f'Publish failed ({resp.status_code})'))


def publish_image(author_urn, token, text, image_path):
    """Upload image then publish post with it."""
    # Step 1: Initialize upload
    init_payload = {
        'initializeUploadRequest': {
            'owner': author_urn,
        }
    }
    resp = requests.post(
        f'{API_URL}/rest/images?action=initializeUpload',
        json=init_payload,
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f'[LinkedIn] Image init failed ({resp.status_code}): {resp.text}')
        # Fallback: publish as text-only post
        print('[LinkedIn] Falling back to text-only post')
        return publish_text(author_urn, token, text)

    upload_data = resp.json().get('value', {})
    upload_url = upload_data.get('uploadUrl')
    image_urn = upload_data.get('image')

    # Step 2: Upload binary
    with open(image_path, 'rb') as f:
        resp = requests.put(upload_url, data=f, headers={
            'Authorization': f'Bearer {token}',
        }, timeout=60)
    if resp.status_code not in (200, 201):
        print(f'[LinkedIn] Image upload failed ({resp.status_code}): {resp.text}')
        return publish_text(author_urn, token, text)

    # Step 3: Create post with image
    payload = {
        'author': author_urn,
        'commentary': text,
        'visibility': 'PUBLIC',
        'distribution': {
            'feedDistribution': 'MAIN_FEED',
            'targetEntities': [],
            'thirdPartyDistributionChannels': [],
        },
        'content': {
            'media': {
                'id': image_urn,
            }
        },
        'lifecycleState': 'PUBLISHED',
    }
    resp = requests.post(
        f'{API_URL}/rest/posts',
        json=payload,
        headers=_headers(token),
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return resp.headers.get('x-restli-id', '') or resp.json().get('id', '')
    data = resp.json() if resp.content else {}
    raise Exception(data.get('message', f'Image post failed ({resp.status_code})'))


def get_post_comments(post_urn, token):
    """Get comments on a LinkedIn post."""
    resp = requests.get(
        f'{API_URL}/rest/socialActions/{post_urn}/comments',
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get('elements', [])


def reply_to_comment(post_urn, token, message, parent_comment=None):
    """Reply to a comment on a LinkedIn post."""
    payload = {
        'actor': post_urn.split(':')[0] + ':' + post_urn.split(':')[1] + ':' + post_urn.split(':')[2],
        'message': {'text': message},
    }
    if parent_comment:
        payload['parentComment'] = parent_comment
    resp = requests.post(
        f'{API_URL}/rest/socialActions/{post_urn}/comments',
        json=payload,
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code in (200, 201):
        return resp.json().get('id', '')
    return ''


def get_org_followers(org_id, token):
    """Get follower statistics for an organization."""
    resp = requests.get(
        f'{API_URL}/rest/organizationalEntityFollowerStatistics',
        params={'q': 'organizationalEntity', 'organizationalEntity': f'urn:li:organization:{org_id}'},
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return {}
    data = resp.json()
    elements = data.get('elements', [])
    return elements[0] if elements else {}


def get_share_statistics(org_id, token):
    """Get share/post statistics for an organization."""
    resp = requests.get(
        f'{API_URL}/rest/organizationalEntityShareStatistics',
        params={'q': 'organizationalEntity', 'organizationalEntity': f'urn:li:organization:{org_id}'},
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return {}
    data = resp.json()
    elements = data.get('elements', [])
    return elements[0] if elements else {}
