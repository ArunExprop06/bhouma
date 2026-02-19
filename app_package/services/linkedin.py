"""LinkedIn API service — uses v2 endpoints for personal profile posting."""
import requests
from urllib.parse import quote
from flask import current_app

API_URL = 'https://api.linkedin.com'


def get_auth_url(redirect_uri, state=''):
    client_id = current_app.config['LINKEDIN_CLIENT_ID']
    scopes = 'openid profile email w_member_social w_organization_social r_organization_social'
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


def _v2_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
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
        f'{API_URL}/v2/organizationalEntityAcls',
        params={'q': 'roleAssignee', 'role': 'ADMINISTRATOR', 'state': 'APPROVED',
                'projection': '(elements*(organizationalTarget))'},
        headers=_v2_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    orgs = []
    for item in data.get('elements', []):
        org_urn = item.get('organizationalTarget')
        if org_urn:
            org_id = org_urn.split(':')[-1]
            org_info = get_organization_info(org_id, token)
            if org_info:
                orgs.append(org_info)
    return orgs


def get_organization_info(org_id, token):
    """Get organization details."""
    resp = requests.get(
        f'{API_URL}/v2/organizations/{org_id}',
        headers=_v2_headers(token),
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


def publish_text(author_urn, token, text):
    """Publish a text post using UGC API (v2)."""
    payload = {
        'author': author_urn,
        'lifecycleState': 'PUBLISHED',
        'specificContent': {
            'com.linkedin.ugc.ShareContent': {
                'shareCommentary': {
                    'text': text,
                },
                'shareMediaCategory': 'NONE',
            }
        },
        'visibility': {
            'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC',
        },
    }
    resp = requests.post(
        f'{API_URL}/v2/ugcPosts',
        json=payload,
        headers=_v2_headers(token),
        timeout=30,
    )
    print(f'[LinkedIn] publish_text status={resp.status_code} body={resp.text[:500]}')
    if resp.status_code in (200, 201):
        return resp.json().get('id', '')
    data = resp.json() if resp.content else {}
    raise Exception(data.get('message', f'Publish failed ({resp.status_code})'))


def publish_image(author_urn, token, text, image_path):
    """Upload image then publish post using UGC API (v2)."""
    # Step 1: Register image upload
    register_payload = {
        'registerUploadRequest': {
            'recipes': ['urn:li:digitalmediaRecipe:feedshare-image'],
            'owner': author_urn,
            'serviceRelationships': [{
                'relationshipType': 'OWNER',
                'identifier': 'urn:li:userGeneratedContent',
            }],
        }
    }
    resp = requests.post(
        f'{API_URL}/v2/assets?action=registerUpload',
        json=register_payload,
        headers=_v2_headers(token),
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f'[LinkedIn] Image register failed ({resp.status_code}): {resp.text}')
        print('[LinkedIn] Falling back to text-only post')
        return publish_text(author_urn, token, text)

    upload_data = resp.json().get('value', {})
    upload_mechanism = upload_data.get('uploadMechanism', {})
    upload_url = upload_mechanism.get(
        'com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest', {}
    ).get('uploadUrl')
    asset = upload_data.get('asset', '')

    if not upload_url:
        print('[LinkedIn] No upload URL returned, falling back to text')
        return publish_text(author_urn, token, text)

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
        'lifecycleState': 'PUBLISHED',
        'specificContent': {
            'com.linkedin.ugc.ShareContent': {
                'shareCommentary': {
                    'text': text,
                },
                'shareMediaCategory': 'IMAGE',
                'media': [{
                    'status': 'READY',
                    'media': asset,
                }],
            }
        },
        'visibility': {
            'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC',
        },
    }
    resp = requests.post(
        f'{API_URL}/v2/ugcPosts',
        json=payload,
        headers=_v2_headers(token),
        timeout=30,
    )
    print(f'[LinkedIn] publish_image status={resp.status_code} body={resp.text[:500]}')
    if resp.status_code in (200, 201):
        return resp.json().get('id', '')
    data = resp.json() if resp.content else {}
    raise Exception(data.get('message', f'Image post failed ({resp.status_code})'))


def get_post_comments(post_urn, token):
    """Get comments on a LinkedIn post."""
    resp = requests.get(
        f'{API_URL}/v2/socialActions/{post_urn}/comments',
        headers=_v2_headers(token),
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
        f'{API_URL}/v2/socialActions/{post_urn}/comments',
        json=payload,
        headers=_v2_headers(token),
        timeout=15,
    )
    if resp.status_code in (200, 201):
        return resp.json().get('id', '')
    return ''


def get_org_followers(org_id, token):
    """Get follower statistics for an organization."""
    resp = requests.get(
        f'{API_URL}/v2/organizationalEntityFollowerStatistics',
        params={'q': 'organizationalEntity', 'organizationalEntity': f'urn:li:organization:{org_id}'},
        headers=_v2_headers(token),
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
        f'{API_URL}/v2/organizationalEntityShareStatistics',
        params={'q': 'organizationalEntity', 'organizationalEntity': f'urn:li:organization:{org_id}'},
        headers=_v2_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return {}
    data = resp.json()
    elements = data.get('elements', [])
    return elements[0] if elements else {}
