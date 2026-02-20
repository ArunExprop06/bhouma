from flask import Blueprint, render_template, request
from flask_login import login_required

prospecting_bp = Blueprint('prospecting', __name__, url_prefix='/prospecting')

# Predefined keyword categories
KEYWORD_CATEGORIES = [
    {
        'name': 'CSR & Sustainability',
        'icon': 'bi-globe-americas',
        'color': '#198754',
        'keywords': [
            'CSR head', 'CSR manager', 'CSR director',
            'corporate social responsibility', 'sustainability officer',
            'ESG manager', 'social impact manager',
        ],
    },
    {
        'name': 'Water & Sanitation',
        'icon': 'bi-droplet-fill',
        'color': '#0d6efd',
        'keywords': [
            'water sanitation', 'WASH program', 'water purification',
            'sanitation manager', 'water treatment', 'clean water NGO',
            'water supply engineer', 'WASH specialist',
        ],
    },
    {
        'name': 'Agriculture & Rural',
        'icon': 'bi-tree-fill',
        'color': '#6f8c3e',
        'keywords': [
            'agriculture officer', 'rural development',
            'organic farming', 'agri business', 'farmer producer organization',
            'FPO manager', 'agriculture consultant',
        ],
    },
    {
        'name': 'NGO & Social Sector',
        'icon': 'bi-people-fill',
        'color': '#e4405f',
        'keywords': [
            'NGO director', 'social enterprise', 'foundation head',
            'nonprofit manager', 'development sector',
            'community development', 'social welfare officer',
        ],
    },
    {
        'name': 'Government & Policy',
        'icon': 'bi-building',
        'color': '#6610f2',
        'keywords': [
            'government officer water', 'municipal commissioner',
            'district collector', 'gram panchayat', 'zilla parishad',
            'public health engineer', 'smart city manager',
        ],
    },
]

# Platform configurations
PLATFORMS = {
    'linkedin': {
        'name': 'LinkedIn',
        'icon': 'bi-linkedin',
        'color': '#0a66c2',
        'search_types': [
            {'label': 'People', 'icon': 'bi-people', 'url': 'https://www.linkedin.com/search/results/people/?keywords={kw}'},
            {'label': 'Companies', 'icon': 'bi-building', 'url': 'https://www.linkedin.com/search/results/companies/?keywords={kw}'},
            {'label': 'Posts', 'icon': 'bi-file-text', 'url': 'https://www.linkedin.com/search/results/content/?keywords={kw}'},
        ],
        'chip_url': 'https://www.linkedin.com/search/results/people/?keywords={kw}',
    },
    'facebook': {
        'name': 'Facebook',
        'icon': 'bi-facebook',
        'color': '#1877f2',
        'search_types': [
            {'label': 'People', 'icon': 'bi-people', 'url': 'https://www.facebook.com/search/people/?q={kw}'},
            {'label': 'Pages', 'icon': 'bi-flag', 'url': 'https://www.facebook.com/search/pages/?q={kw}'},
            {'label': 'Groups', 'icon': 'bi-people-fill', 'url': 'https://www.facebook.com/search/groups/?q={kw}'},
        ],
        'chip_url': 'https://www.facebook.com/search/people/?q={kw}',
    },
    'instagram': {
        'name': 'Instagram',
        'icon': 'bi-instagram',
        'color': '#e4405f',
        'search_types': [
            {'label': 'Hashtags', 'icon': 'bi-hash', 'url': 'https://www.instagram.com/explore/tags/{kw}/'},
            {'label': 'Accounts', 'icon': 'bi-person', 'url': 'https://www.google.com/search?q=site:instagram.com+{kw}'},
        ],
        'chip_url': 'https://www.instagram.com/explore/tags/{kw}/',
    },
}


@prospecting_bp.route('/')
@login_required
def index():
    custom_keyword = request.args.get('q', '').strip()
    platform = request.args.get('platform', 'linkedin')
    if platform not in PLATFORMS:
        platform = 'linkedin'
    return render_template('prospecting/index.html',
                           categories=KEYWORD_CATEGORIES,
                           custom_keyword=custom_keyword,
                           platform=platform,
                           platforms=PLATFORMS,
                           current_platform=PLATFORMS[platform])
