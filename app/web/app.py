"""Flask web application"""
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
import os
import app

logger = logging.getLogger(__name__)


def create_app(config_manager, sync_manager, scheduler):
    """Create and configure Flask application"""

    flask_app = Flask(__name__)
    flask_app.secret_key = os.urandom(24)

    # Store managers in app config
    flask_app.config['CONFIG_MANAGER'] = config_manager
    flask_app.config['SYNC_MANAGER'] = sync_manager
    flask_app.config['SCHEDULER'] = scheduler

    # Make version available in all templates
    @flask_app.context_processor
    def inject_version():
        return dict(app_version=app.__version__)

    # Authentication decorator
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('authenticated'):
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    @flask_app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page"""
        if request.method == 'POST':
            password = request.form.get('password')
            admin_password = config_manager.get('web', 'admin_password', default='changeme')

            if password == admin_password:
                session['authenticated'] = True
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid password', 'error')

        return render_template('login.html')

    @flask_app.route('/logout')
    def logout():
        """Logout"""
        session.pop('authenticated', None)
        flash('Logged out successfully', 'success')
        return redirect(url_for('login'))

    @flask_app.route('/')
    @login_required
    def index():
        """Main dashboard"""
        try:
            stats = sync_manager.get_sync_stats()
            scheduler_status = scheduler.get_status()

            return render_template('index.html',
                                   stats=stats,
                                   scheduler=scheduler_status,
                                   config=config_manager.config)
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")
            return render_template('error.html', error=str(e)), 500

    @flask_app.route('/api/sync', methods=['POST'])
    @login_required
    def trigger_sync():
        """Trigger manual sync"""
        try:
            data = request.get_json() or {}
            full_sync = data.get('full_sync', False)

            result = scheduler.trigger_manual_sync(full_sync=full_sync)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Error triggering sync: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/status')
    def get_status():
        """Get current status (public endpoint for healthcheck)"""
        try:
            # Basic health check - just verify the app is running
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/status/detailed')
    @login_required
    def get_detailed_status():
        """Get detailed status (requires authentication)"""
        try:
            stats = sync_manager.get_sync_stats()
            scheduler_status = scheduler.get_status()
            connection_test = sync_manager.test_connection()

            return jsonify({
                'stats': stats,
                'scheduler': scheduler_status,
                'connection': connection_test
            })

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/exports')
    @login_required
    def list_exports():
        """List recent CSV exports"""
        try:
            exports = sync_manager.letterboxd_csv.get_recent_exports(limit=20)

            # Convert datetime objects to ISO format strings for JSON serialization
            for export in exports:
                if 'created' in export and isinstance(export['created'], datetime):
                    export['created'] = export['created'].isoformat()
                if 'modified' in export and isinstance(export['modified'], datetime):
                    export['modified'] = export['modified'].isoformat()

            return jsonify({'exports': exports})

        except Exception as e:
            logger.error(f"Error listing exports: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/exports/<filename>')
    @login_required
    def download_export(filename):
        """Download CSV export"""
        try:
            export_path = config_manager.get('sync', 'export_path')
            filepath = os.path.join(export_path, filename)

            # Security check - ensure file is in export directory
            if not os.path.abspath(filepath).startswith(os.path.abspath(export_path)):
                return jsonify({'error': 'Invalid file path'}), 403

            if not os.path.exists(filepath):
                return jsonify({'error': 'File not found'}), 404

            return send_file(filepath, as_attachment=True)

        except Exception as e:
            logger.error(f"Error downloading export: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/config', methods=['GET', 'POST'])
    @login_required
    def manage_config():
        """Get or update configuration"""
        if request.method == 'GET':
            # Return config (without sensitive data)
            safe_config = config_manager.config.copy()
            if 'trakt' in safe_config:
                safe_config['trakt'].pop('client_secret', None)
                safe_config['trakt'].pop('access_token', None)
                safe_config['trakt'].pop('refresh_token', None)
            if 'letterboxd' in safe_config:
                safe_config['letterboxd'].pop('password', None)
            if 'web' in safe_config:
                safe_config['web'].pop('admin_password', None)

            return jsonify(safe_config)

        elif request.method == 'POST':
            try:
                data = request.get_json()

                # Update specific config values
                if 'sync' in data and 'schedule' in data['sync']:
                    scheduler.update_schedule(data['sync']['schedule'])

                # Save other config updates
                for key, value in data.items():
                    if key in config_manager.config:
                        for subkey, subvalue in value.items():
                            config_manager.set(key, subkey, value=subvalue)

                return jsonify({'success': True, 'message': 'Configuration updated'})

            except Exception as e:
                logger.error(f"Error updating config: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/auth/trakt/start', methods=['POST'])
    @login_required
    def start_trakt_auth():
        """Start Trakt OAuth flow"""
        try:
            auth_url = sync_manager.authenticate_trakt()
            return jsonify({'auth_url': auth_url})

        except Exception as e:
            logger.error(f"Error starting Trakt auth: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/auth/trakt/complete', methods=['POST'])
    @login_required
    def complete_trakt_auth():
        """Complete Trakt OAuth flow"""
        try:
            data = request.get_json()
            code = data.get('code')

            if not code:
                return jsonify({'error': 'Authorization code required'}), 400

            sync_manager.complete_trakt_auth(code)
            return jsonify({'success': True, 'message': 'Trakt authentication completed'})

        except Exception as e:
            logger.error(f"Error completing Trakt auth: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/scheduler/toggle', methods=['POST'])
    @login_required
    def toggle_scheduler():
        """Start/stop scheduler"""
        try:
            action = request.get_json().get('action')

            if action == 'start':
                scheduler.start()
                message = 'Scheduler started'
            elif action == 'stop':
                scheduler.stop()
                message = 'Scheduler stopped'
            else:
                return jsonify({'error': 'Invalid action'}), 400

            return jsonify({'success': True, 'message': message})

        except Exception as e:
            logger.error(f"Error toggling scheduler: {e}")
            return jsonify({'error': str(e)}), 500

    return flask_app
