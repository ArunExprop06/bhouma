import os
from app_package import create_app
from flask import send_from_directory

app = create_app()


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    # Only start scheduler in the main process (not the reloader child)
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        pass  # reloader parent — skip scheduler
    else:
        from scheduler import init_scheduler
        init_scheduler(app)

    app.run(host='0.0.0.0', port=8090, debug=True)
