from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app_package import db
from app_package.models import User, TaskTemplate, DailyTaskInstance, TaskAssignment, AppSetting
from datetime import datetime, date, timedelta, timezone
from functools import wraps
import urllib.parse
import io, base64

daily_tasks_bp = Blueprint('daily_tasks', __name__, url_prefix='/tasks')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


def ensure_today_tasks(user_id):
    """Create missing DailyTaskInstance rows for today based on assigned active templates."""
    today = date.today()

    # Only templates assigned to this user AND active
    assigned_ids = {a.template_id for a in
                    db.session.query(TaskAssignment).filter_by(user_id=user_id).all()}
    active_assigned = {t.id for t in
                       db.session.query(TaskTemplate).filter(
                           TaskTemplate.id.in_(assigned_ids),
                           TaskTemplate.is_active == True
                       ).all()} if assigned_ids else set()

    existing = db.session.query(DailyTaskInstance).filter_by(
        user_id=user_id, task_date=today
    ).all()
    existing_template_ids = {inst.template_id for inst in existing}

    missing = active_assigned - existing_template_ids
    for tid in missing:
        inst = DailyTaskInstance(template_id=tid, user_id=user_id, task_date=today)
        db.session.add(inst)
    if missing:
        db.session.commit()


# ── Employee Routes ──────────────────────────────────────────────

@daily_tasks_bp.route('')
@login_required
def my_tasks():
    ensure_today_tasks(current_user.id)
    today = date.today()
    instances = (
        db.session.query(DailyTaskInstance)
        .join(TaskTemplate)
        .filter(DailyTaskInstance.user_id == current_user.id, DailyTaskInstance.task_date == today)
        .order_by(TaskTemplate.sort_order, TaskTemplate.id)
        .all()
    )
    total = len(instances)
    done = sum(1 for i in instances if i.is_completed)
    pct = round(done / total * 100) if total else 0

    # Group by platform
    grouped = {}
    for inst in instances:
        p = inst.template.platform
        grouped.setdefault(p, []).append(inst)

    return render_template('tasks/my_tasks.html',
                           instances=instances, grouped=grouped,
                           total=total, done=done, pct=pct, today=today)


@daily_tasks_bp.route('/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    inst = db.session.get(DailyTaskInstance, task_id)
    if not inst or inst.user_id != current_user.id:
        flash('Task not found.', 'danger')
        return redirect(url_for('daily_tasks.my_tasks'))

    inst.is_completed = not inst.is_completed
    inst.completed_at = datetime.now(timezone.utc) if inst.is_completed else None
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        total = db.session.query(DailyTaskInstance).filter_by(
            user_id=current_user.id, task_date=inst.task_date).count()
        done = db.session.query(DailyTaskInstance).filter_by(
            user_id=current_user.id, task_date=inst.task_date, is_completed=True).count()
        pct = round(done / total * 100) if total else 0
        return jsonify(ok=True, completed=inst.is_completed, done=done, total=total, pct=pct)

    return redirect(url_for('daily_tasks.my_tasks'))


@daily_tasks_bp.route('/<int:task_id>/notes', methods=['POST'])
@login_required
def save_notes(task_id):
    inst = db.session.get(DailyTaskInstance, task_id)
    if not inst or inst.user_id != current_user.id:
        flash('Task not found.', 'danger')
        return redirect(url_for('daily_tasks.my_tasks'))

    inst.notes = request.form.get('notes', '').strip()
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(ok=True)
    flash('Notes saved.', 'success')
    return redirect(url_for('daily_tasks.my_tasks'))


@daily_tasks_bp.route('/whatsapp-qr')
@login_required
def whatsapp_qr():
    ensure_today_tasks(current_user.id)
    today = date.today()
    instances = (
        db.session.query(DailyTaskInstance)
        .join(TaskTemplate)
        .filter(DailyTaskInstance.user_id == current_user.id, DailyTaskInstance.task_date == today)
        .order_by(TaskTemplate.sort_order, TaskTemplate.id)
        .all()
    )
    total = len(instances)
    done = sum(1 for i in instances if i.is_completed)
    pct = round(done / total * 100) if total else 0

    # Build message grouped by platform
    lines = [f"*Daily Task Report*", f"*{current_user.name}* — {today.strftime('%d %b %Y')}",
             f"Completion: {done}/{total} ({pct}%)", ""]
    grouped = {}
    for inst in instances:
        grouped.setdefault(inst.template.platform, []).append(inst)

    platform_labels = {'facebook': 'Facebook', 'instagram': 'Instagram',
                       'linkedin': 'LinkedIn', 'general': 'General'}
    for plat in ['facebook', 'instagram', 'linkedin', 'general']:
        if plat not in grouped:
            continue
        lines.append(f"*{platform_labels[plat]}*")
        for inst in grouped[plat]:
            mark = '\u2705' if inst.is_completed else '\u2b1c'
            lines.append(f"  {mark} {inst.template.title}")
            if inst.notes:
                lines.append(f"      _Note: {inst.notes}_")
        lines.append("")

    message = "\n".join(lines)
    encoded = urllib.parse.quote(message, safe='')

    # Use configured group number if set, otherwise generic
    wa_number = (AppSetting.get('whatsapp_group_number') or '').strip()
    if wa_number:
        wa_url = f"https://wa.me/{wa_number}?text={encoded}"
    else:
        wa_url = f"https://wa.me/?text={encoded}"

    # Generate QR
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(wa_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#25D366", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render_template('tasks/whatsapp_qr.html',
                           message=message, wa_url=wa_url,
                           qr_b64=qr_b64, done=done, total=total, pct=pct, today=today)


# ── Admin Routes ─────────────────────────────────────────────────

SAMPLE_TASKS = [
    ('Follow 10 accounts', 'Follow relevant accounts in your niche', 'linkedin', 1),
    ('Send 5 connection requests', 'Personalized connection requests to prospects', 'linkedin', 2),
    ('Comment on 5 posts', 'Leave meaningful comments on industry posts', 'linkedin', 3),
    ('Publish 1 LinkedIn post', 'Share an insight, tip, or update', 'linkedin', 4),
    ('Post 2 Facebook posts', 'Share engaging content on the page', 'facebook', 5),
    ('Reply to Facebook comments', 'Respond to all new comments on posts', 'facebook', 6),
    ('Post 1 Instagram reel/story', 'Create and post a reel or story', 'instagram', 7),
    ('Engage with 10 Instagram posts', 'Like and comment on relevant posts', 'instagram', 8),
    ('Update CRM/leads sheet', 'Log new leads and update statuses', 'general', 9),
    ('Send daily report', 'Submit end-of-day completion report', 'general', 10),
]


def seed_sample_tasks(admin_id):
    """Create sample task templates if none exist."""
    if db.session.query(TaskTemplate).count() > 0:
        return
    for title, desc, platform, order in SAMPLE_TASKS:
        db.session.add(TaskTemplate(
            title=title, description=desc, platform=platform,
            sort_order=order, created_by=admin_id,
        ))
    db.session.commit()


@daily_tasks_bp.route('/admin/templates')
@login_required
@admin_required
def admin_templates():
    seed_sample_tasks(current_user.id)
    templates = db.session.query(TaskTemplate).order_by(
        TaskTemplate.sort_order, TaskTemplate.id).all()
    members = db.session.query(User).filter_by(is_active_user=True).order_by(User.name).all()
    wa_number = AppSetting.get('whatsapp_group_number', '')
    return render_template('tasks/admin_templates.html',
                           templates=templates, members=members, wa_number=wa_number)


@daily_tasks_bp.route('/admin/templates/create', methods=['POST'])
@login_required
@admin_required
def create_template():
    title = request.form.get('title', '').strip()
    if not title:
        flash('Title is required.', 'danger')
        return redirect(url_for('daily_tasks.admin_templates'))

    t = TaskTemplate(
        title=title,
        description=request.form.get('description', '').strip(),
        platform=request.form.get('platform', 'general'),
        sort_order=int(request.form.get('sort_order', 0) or 0),
        created_by=current_user.id,
    )
    db.session.add(t)
    db.session.commit()
    flash(f'Task "{title}" created.', 'success')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/templates/<int:tid>/edit', methods=['POST'])
@login_required
@admin_required
def edit_template(tid):
    t = db.session.get(TaskTemplate, tid)
    if not t:
        flash('Template not found.', 'danger')
        return redirect(url_for('daily_tasks.admin_templates'))

    t.title = request.form.get('title', t.title).strip()
    t.description = request.form.get('description', '').strip()
    t.platform = request.form.get('platform', t.platform)
    t.sort_order = int(request.form.get('sort_order', t.sort_order) or 0)
    db.session.commit()
    flash(f'Task "{t.title}" updated.', 'success')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/templates/<int:tid>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_template(tid):
    t = db.session.get(TaskTemplate, tid)
    if not t:
        flash('Template not found.', 'danger')
        return redirect(url_for('daily_tasks.admin_templates'))
    t.is_active = not t.is_active
    db.session.commit()
    status = 'activated' if t.is_active else 'deactivated'
    flash(f'Task "{t.title}" {status}.', 'info')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/templates/<int:tid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_template(tid):
    t = db.session.get(TaskTemplate, tid)
    if not t:
        flash('Template not found.', 'danger')
        return redirect(url_for('daily_tasks.admin_templates'))
    title = t.title
    db.session.delete(t)
    db.session.commit()
    flash(f'Task "{title}" deleted.', 'success')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/templates/<int:tid>/assign', methods=['POST'])
@login_required
@admin_required
def assign_template(tid):
    t = db.session.get(TaskTemplate, tid)
    if not t:
        flash('Template not found.', 'danger')
        return redirect(url_for('daily_tasks.admin_templates'))

    selected_user_ids = request.form.getlist('user_ids', type=int)

    # Remove old assignments
    db.session.query(TaskAssignment).filter_by(template_id=tid).delete()
    # Add new
    for uid in selected_user_ids:
        db.session.add(TaskAssignment(template_id=tid, user_id=uid))
    db.session.commit()
    flash(f'Assigned "{t.title}" to {len(selected_user_ids)} member(s).', 'success')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/whatsapp-settings', methods=['POST'])
@login_required
@admin_required
def save_whatsapp_settings():
    number = request.form.get('whatsapp_number', '').strip()
    # Strip any + prefix or spaces, keep only digits
    number = ''.join(c for c in number if c.isdigit())
    AppSetting.set('whatsapp_group_number', number)
    flash('WhatsApp group number saved.', 'success')
    return redirect(url_for('daily_tasks.admin_templates'))


@daily_tasks_bp.route('/admin/report')
@login_required
@admin_required
def admin_report():
    view = request.args.get('view', 'day')
    date_str = request.args.get('date')
    try:
        sel_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        sel_date = date.today()

    members = db.session.query(User).filter_by(is_active_user=True).order_by(User.name).all()

    if view == 'week':
        # Monday to Sunday of the week containing sel_date
        start = sel_date - timedelta(days=sel_date.weekday())
        dates = [start + timedelta(days=i) for i in range(7)]

        week_data = {}
        for m in members:
            row = {}
            for d in dates:
                total = db.session.query(DailyTaskInstance).filter_by(
                    user_id=m.id, task_date=d).count()
                done = db.session.query(DailyTaskInstance).filter_by(
                    user_id=m.id, task_date=d, is_completed=True).count()
                pct = round(done / total * 100) if total else None
                row[d] = {'done': done, 'total': total, 'pct': pct}
            week_data[m.id] = row

        # Overall stats
        all_total = sum(r['total'] for wd in week_data.values() for r in wd.values())
        all_done = sum(r['done'] for wd in week_data.values() for r in wd.values())
        overall_pct = round(all_done / all_total * 100) if all_total else 0

        return render_template('tasks/admin_report.html',
                               view=view, sel_date=sel_date, members=members,
                               dates=dates, week_data=week_data,
                               all_total=all_total, all_done=all_done, overall_pct=overall_pct)
    else:
        day_data = {}
        for m in members:
            total = db.session.query(DailyTaskInstance).filter_by(
                user_id=m.id, task_date=sel_date).count()
            done = db.session.query(DailyTaskInstance).filter_by(
                user_id=m.id, task_date=sel_date, is_completed=True).count()
            pct = round(done / total * 100) if total else None
            day_data[m.id] = {'done': done, 'total': total, 'pct': pct}

        all_total = sum(d['total'] for d in day_data.values())
        all_done = sum(d['done'] for d in day_data.values())
        overall_pct = round(all_done / all_total * 100) if all_total else 0

        return render_template('tasks/admin_report.html',
                               view=view, sel_date=sel_date, members=members,
                               day_data=day_data,
                               all_total=all_total, all_done=all_done, overall_pct=overall_pct)
