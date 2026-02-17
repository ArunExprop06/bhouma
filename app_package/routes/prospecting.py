from flask import Blueprint, render_template, request
from flask_login import login_required

prospecting_bp = Blueprint('prospecting', __name__, url_prefix='/prospecting')

# Predefined keyword categories for LinkedIn search
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


@prospecting_bp.route('/')
@login_required
def index():
    custom_keyword = request.args.get('q', '').strip()
    return render_template('prospecting/index.html',
                           categories=KEYWORD_CATEGORIES,
                           custom_keyword=custom_keyword)
