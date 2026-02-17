"""APScheduler job definitions for scheduled posts."""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

scheduler = BackgroundScheduler()


def publish_scheduled_posts():
    """Check for posts with status=scheduled and scheduled_at <= now, then publish them."""
    from app_package import db
    from app_package.models import Post
    from app_package.routes.compose import publish_post

    now = datetime.now(timezone.utc)
    posts = db.session.query(Post).filter(
        Post.status == 'scheduled',
        Post.scheduled_at <= now,
    ).all()

    for post in posts:
        post.status = 'publishing'
        db.session.commit()
        try:
            publish_post(post)
        except Exception as e:
            post.status = 'failed'
            db.session.commit()
            print(f'Scheduler: Failed to publish post {post.id}: {e}')


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""
    def job_wrapper():
        with app.app_context():
            publish_scheduled_posts()

    scheduler.add_job(
        func=job_wrapper,
        trigger='interval',
        minutes=1,
        id='publish_scheduled_posts',
        replace_existing=True,
    )
    scheduler.start()
