from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app_package import db
from app_package.models import SocialAccount
from app_package.services import facebook as fb_svc, instagram as ig_svc, linkedin as li_svc
from datetime import datetime, timezone, timedelta

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')


@accounts_bp.route('/')
@login_required
def list_accounts():
    accounts = db.session.query(SocialAccount).filter_by(is_active=True).all()
    return render_template('accounts/list.html', accounts=accounts)


@accounts_bp.route('/connect')
@login_required
def connect():
    return render_template('accounts/connect.html')


# ─── Facebook OAuth ───────────────────────────────────────────────
@accounts_bp.route('/connect/facebook')
@login_required
def connect_facebook():
    redirect_uri = current_app.config['BASE_URL'] + '/accounts/callback/facebook'
    auth_url = fb_svc.get_auth_url(redirect_uri)
    return redirect(auth_url)


@accounts_bp.route('/callback/facebook')
@login_required
def callback_facebook():
    code = request.args.get('code')
    if not code:
        flash('Facebook authorization cancelled.', 'warning')
        return redirect(url_for('accounts.list_accounts'))
    try:
        redirect_uri = current_app.config['BASE_URL'] + '/accounts/callback/facebook'
        user_token = fb_svc.exchange_code(code, redirect_uri)
        pages = fb_svc.get_pages(user_token)
        if not pages:
            flash('No Facebook Pages found. Make sure you manage at least one page.', 'warning')
            return redirect(url_for('accounts.list_accounts'))
        for page in pages:
            existing = db.session.query(SocialAccount).filter_by(
                platform='facebook', platform_account_id=page['id']
            ).first()
            if existing:
                existing.access_token = page['access_token']
                existing.account_name = page['name']
                existing.is_active = True
            else:
                pic = page.get('picture', {}).get('data', {}).get('url', '')
                account = SocialAccount(
                    user_id=current_user.id,
                    platform='facebook',
                    platform_account_id=page['id'],
                    page_id=page['id'],
                    account_name=page['name'],
                    account_image_url=pic,
                    access_token=page['access_token'],
                )
                db.session.add(account)
        db.session.commit()
        flash(f'Connected {len(pages)} Facebook Page(s)!', 'success')
    except Exception as e:
        flash(f'Facebook connection failed: {e}', 'danger')
    return redirect(url_for('accounts.list_accounts'))


# ─── Instagram OAuth (via Meta) ───────────────────────────────────
@accounts_bp.route('/connect/instagram')
@login_required
def connect_instagram():
    redirect_uri = current_app.config['BASE_URL'] + '/accounts/callback/instagram'
    auth_url = ig_svc.get_auth_url(redirect_uri)
    return redirect(auth_url)


@accounts_bp.route('/callback/instagram')
@login_required
def callback_instagram():
    code = request.args.get('code')
    if not code:
        flash('Instagram authorization cancelled.', 'warning')
        return redirect(url_for('accounts.list_accounts'))
    try:
        redirect_uri = current_app.config['BASE_URL'] + '/accounts/callback/instagram'
        user_token = fb_svc.exchange_code(code, redirect_uri)
        pages = fb_svc.get_pages(user_token)
        connected = 0
        for page in pages:
            ig_id = ig_svc.get_ig_account_from_page(page['id'], page['access_token'])
            if not ig_id:
                continue
            existing = db.session.query(SocialAccount).filter_by(
                platform='instagram', platform_account_id=ig_id
            ).first()
            profile = ig_svc.get_ig_profile(ig_id, page['access_token'])
            if existing:
                existing.access_token = page['access_token']
                existing.account_name = profile.get('username', profile.get('name', ''))
                existing.account_image_url = profile.get('profile_picture_url', '')
                existing.is_active = True
            else:
                account = SocialAccount(
                    user_id=current_user.id,
                    platform='instagram',
                    platform_account_id=ig_id,
                    page_id=page['id'],
                    account_name=profile.get('username', profile.get('name', '')),
                    account_image_url=profile.get('profile_picture_url', ''),
                    access_token=page['access_token'],
                )
                account.set_extra('ig_user_id', ig_id)
                db.session.add(account)
            connected += 1
        db.session.commit()
        if connected:
            flash(f'Connected {connected} Instagram account(s)!', 'success')
        else:
            flash('No Instagram Business accounts found linked to your Facebook Pages.', 'warning')
    except Exception as e:
        flash(f'Instagram connection failed: {e}', 'danger')
    return redirect(url_for('accounts.list_accounts'))


# ─── LinkedIn OAuth ───────────────────────────────────────────────
@accounts_bp.route('/connect/linkedin')
@login_required
def connect_linkedin():
    redirect_uri = current_app.config['BASE_URL'].rstrip('/') + '/accounts/callback/linkedin'
    auth_url = li_svc.get_auth_url(redirect_uri, state='bhouma')
    return redirect(auth_url)


@accounts_bp.route('/callback/linkedin')
@login_required
def callback_linkedin():
    # Debug: log all callback params
    print(f'[LinkedIn Callback] Full URL: {request.url}')
    print(f'[LinkedIn Callback] Args: {dict(request.args)}')
    error = request.args.get('error')
    error_desc = request.args.get('error_description')
    if error:
        print(f'[LinkedIn Callback] ERROR: {error} - {error_desc}')
        flash(f'LinkedIn error: {error_desc or error}', 'danger')
        return redirect(url_for('accounts.list_accounts'))
    code = request.args.get('code')
    if not code:
        flash('LinkedIn authorization cancelled.', 'warning')
        return redirect(url_for('accounts.list_accounts'))
    try:
        redirect_uri = current_app.config['BASE_URL'].rstrip('/') + '/accounts/callback/linkedin'
        tokens = li_svc.exchange_code(code, redirect_uri)
        access_token = tokens['access_token']
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens['expires_in'])

        # Try org pages first, fall back to personal profile
        profiles = []
        try:
            profiles = li_svc.get_organization_pages(access_token)
        except Exception:
            pass

        if not profiles:
            user_profile = li_svc.get_user_profile(access_token)
            if user_profile:
                profiles = [user_profile]

        if not profiles:
            flash('Could not retrieve LinkedIn profile.', 'warning')
            return redirect(url_for('accounts.list_accounts'))

        for prof in profiles:
            existing = db.session.query(SocialAccount).filter_by(
                platform='linkedin', platform_account_id=prof['id']
            ).first()
            if existing:
                existing.access_token = access_token
                existing.refresh_token = tokens.get('refresh_token', '')
                existing.token_expires_at = expires_at
                existing.account_name = prof['name']
                existing.is_active = True
            else:
                account = SocialAccount(
                    user_id=current_user.id,
                    platform='linkedin',
                    platform_account_id=prof['id'],
                    page_id=prof['id'],
                    account_name=prof['name'],
                    account_image_url=prof.get('logo_url', ''),
                    access_token=access_token,
                    refresh_token=tokens.get('refresh_token', ''),
                    token_expires_at=expires_at,
                )
                account.set_extra('org_urn', prof['urn'])
                db.session.add(account)
        db.session.commit()
        flash(f'Connected {len(profiles)} LinkedIn account(s)!', 'success')
    except Exception as e:
        flash(f'LinkedIn connection failed: {e}', 'danger')
    return redirect(url_for('accounts.list_accounts'))


# ─── Disconnect ───────────────────────────────────────────────────
@accounts_bp.route('/disconnect/<int:account_id>', methods=['POST'])
@login_required
def disconnect(account_id):
    account = db.session.get(SocialAccount, account_id)
    if account:
        account.is_active = False
        db.session.commit()
        flash(f'Disconnected {account.account_name}.', 'info')
    return redirect(url_for('accounts.list_accounts'))
