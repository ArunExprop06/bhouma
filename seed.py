from app_package import create_app, db
from app_package.models import User

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
