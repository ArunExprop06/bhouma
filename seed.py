from app_package import create_app, db
from app_package.models import User, TaskTemplate, TaskAssignment

app = create_app()

with app.app_context():
    db.create_all()

    # Seed admin user
    admin = db.session.query(User).filter_by(email='admin@bhouma.com').first()
    if not admin:
        admin = User(name='Admin', email='admin@bhouma.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created: admin@bhouma.com / admin123')
    else:
        print('Admin user already exists.')

    # Seed daily task templates
    if db.session.query(TaskTemplate).count() == 0:
        admin = db.session.query(User).filter_by(role='admin').first()
        tasks = [
            # LinkedIn Growth
            ('Follow 5 target accounts', 'Follow decision-makers, founders, and industry leaders in your niche', 'linkedin', 1),
            ('Send 10 connection requests', 'Send personalized connection requests — mention a shared interest or mutual connection', 'linkedin', 2),
            ('Comment on 10 posts', 'Leave thoughtful 2-3 line comments on trending posts in your industry', 'linkedin', 3),
            ('Like 20 posts in feed', 'Engage with posts from connections and prospects to stay visible', 'linkedin', 4),
            ('Publish 1 LinkedIn post', 'Share a tip, insight, case study, or behind-the-scenes update', 'linkedin', 5),
            ('Reply to all LinkedIn DMs', 'Respond to every message within 24 hours — build relationships', 'linkedin', 6),
            ('Engage in 2 LinkedIn groups', 'Comment or post in relevant industry groups for visibility', 'linkedin', 7),

            # Facebook Growth
            ('Post 2 Facebook page posts', 'Share engaging content — mix of value posts, stories, and CTAs', 'facebook', 8),
            ('Reply to all page comments', 'Respond to every comment on your page posts within 2 hours', 'facebook', 9),
            ('Share 1 post to 3 groups', 'Cross-post your best content to relevant Facebook groups', 'facebook', 10),
            ('Like & comment on 10 group posts', 'Be active in Facebook groups — comment meaningfully, not just emojis', 'facebook', 11),
            ('Post 1 Facebook Story/Reel', 'Create a short video or story for organic reach boost', 'facebook', 12),

            # Instagram Growth
            ('Post 1 Instagram Reel', 'Create a 30-60 sec reel with trending audio — reels get 2x reach', 'instagram', 13),
            ('Post 2 Instagram Stories', 'Use polls, questions, or behind-the-scenes for engagement', 'instagram', 14),
            ('Engage with 15 posts in niche', 'Like and leave genuine comments on posts in your target hashtags', 'instagram', 15),
            ('Reply to all DMs & comments', 'Fast replies boost your algorithm ranking', 'instagram', 16),

            # General / Operations
            ('Update lead tracker / CRM', 'Log new leads, update deal stages, add follow-up notes', 'general', 17),
            ('Review analytics & adjust', 'Check what worked yesterday — double down or pivot', 'general', 18),
            ('Send daily WhatsApp report', 'Submit end-of-day completion report to the team group', 'general', 19),
        ]
        for title, desc, platform, order in tasks:
            db.session.add(TaskTemplate(
                title=title, description=desc, platform=platform,
                sort_order=order, created_by=admin.id,
            ))
        db.session.commit()

        # Auto-assign all tasks to all active users
        all_templates = db.session.query(TaskTemplate).all()
        all_users = db.session.query(User).filter_by(is_active_user=True).all()
        for t in all_templates:
            for u in all_users:
                db.session.add(TaskAssignment(template_id=t.id, user_id=u.id))
        db.session.commit()
        print(f'{len(tasks)} daily task templates seeded and assigned to {len(all_users)} user(s).')
    else:
        print('Task templates already exist.')
