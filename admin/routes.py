"""
Admin Routes - Clean and organized admin panel routes
"""
import os
import sys
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import UPLOAD_FOLDER, ADMIN_PORT, SECRET_KEY
from database import Database, get_stats, get_bookings, update_booking_status, get_settings, update_settings
from models import BusBooking, ResortBooking, WebsiteSettings
from backend.utils import save_upload, delete_upload, format_price

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = SECRET_KEY

# Context processors
@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    try:
        row = get_settings()
        return {'settings': WebsiteSettings.from_row(row)}
    except:
        return {'settings': WebsiteSettings()}

# Auth decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ============== AUTH ROUTES ==============

@app.route('/')
def index():
    """Redirect to login or dashboard"""
    if session.get('admin_id'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Simple auth (in production, use proper password hashing)
        if username == 'admin' and password == 'admin123':
            session['admin_id'] = 1
            session['admin_username'] = username
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    """Admin logout"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# ============== DASHBOARD ==============

@app.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with stats"""
    stats = get_stats()
    
    # Get recent bookings
    recent_bus = get_bookings('bus', limit=5)
    recent_resort = get_bookings('resort', limit=5)
    
    return render_template('dashboard.html',
                         stats=stats,
                         recent_bus=[BusBooking.from_row(r) for r in recent_bus],
                         recent_resort=[ResortBooking.from_row(r) for r in recent_resort])

# ============== BOOKINGS ==============

@app.route('/bookings/bus')
@admin_required
def bookings_bus():
    """Bus bookings list"""
    status = request.args.get('status')
    bookings = get_bookings('bus', status=status, limit=100)
    return render_template('bookings_bus.html',
                         bookings=[BusBooking.from_row(b) for b in bookings],
                         filter_status=status)

@app.route('/bookings/resort')
@admin_required
def bookings_resort():
    """Resort bookings list"""
    status = request.args.get('status')
    bookings = get_bookings('resort', status=status, limit=100)
    return render_template('bookings_resort.html',
                         bookings=[ResortBooking.from_row(b) for b in bookings],
                         filter_status=status)

@app.route('/booking/<type>/<int:id>/confirm', methods=['POST'])
@admin_required
def confirm_booking(type, id):
    """Confirm a booking"""
    try:
        if type not in ['bus', 'resort']:
            flash('Invalid booking type', 'error')
            return redirect(url_for('dashboard'))
        
        update_booking_status(type, id, 'Confirmed')
        flash(f'Booking confirmed successfully', 'success')
    except Exception as e:
        flash(f'Error confirming booking: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/booking/<type>/<int:id>/cancel', methods=['POST'])
@admin_required
def cancel_booking(type, id):
    """Cancel a booking"""
    try:
        if type not in ['bus', 'resort']:
            flash('Invalid booking type', 'error')
            return redirect(url_for('dashboard'))
        
        update_booking_status(type, id, 'Cancelled')
        flash(f'Booking cancelled', 'success')
    except Exception as e:
        flash(f'Error cancelling booking: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

# ============== CONTENT MANAGEMENT ==============

@app.route('/content', methods=['GET', 'POST'])
@admin_required
def content():
    """Manage website content"""
    if request.method == 'POST':
        try:
            data = {
                'site_name': request.form.get('site_name', 'BusResort').strip(),
                'homepage_welcome': request.form.get('homepage_welcome', '').strip(),
                'homepage_description': request.form.get('homepage_description', '').strip(),
                'contact_email': request.form.get('contact_email', '').strip()
            }
            
            # Handle image uploads
            current = get_settings()
            
            for field in ['homepage_image', 'resort_image', 'bus_image']:
                file = request.files.get(field)
                if file and file.filename:
                    # Delete old image
                    if current and current.get(field):
                        delete_upload(current[field])
                    # Save new image
                    data[field] = save_upload(file, field.replace('_image', ''))
                elif current:
                    # Keep existing
                    data[field] = current.get(field)
            
            update_settings(data)
            flash('Settings updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
    
    settings = get_settings()
    return render_template('content.html', settings=WebsiteSettings.from_row(settings))

# ============== SALES REPORTS ==============

@app.route('/sales')
@admin_required
def sales():
    """Sales reports"""
    stats = get_stats()
    return render_template('sales.html', stats=stats)

# ============== API ENDPOINTS ==============

@app.route('/api/calendar-events')
@admin_required
def api_calendar():
    """Get calendar events"""
    try:
        events = []
        
        # Bus bookings (last 100)
        bus = Database.fetch_all(
            "SELECT id, name, datetime, checkin, checkout, status FROM BusBookings ORDER BY id DESC LIMIT 100"
        )
        for b in bus:
            try:
                start = str(b['datetime'] or b['checkin'] or '').strip()
                if start:
                    events.append({
                        'title': f"Bus: {b['name']}",
                        'start': start,
                        'status': b['status'],
                        'url': f"/bookings/bus",
                        'color': '#22c55e' if b['status'] == 'Confirmed' else '#f59e0b'
                    })
            except:
                continue
        
        # Resort bookings (last 100)
        resort = Database.fetch_all(
            "SELECT id, name, checkin, checkout, status FROM ResortBookings ORDER BY id DESC LIMIT 100"
        )
        for r in resort:
            try:
                if r['checkin']:
                    events.append({
                        'title': f"Resort: {r['name']}",
                        'start': str(r['checkin']),
                        'end': str(r['checkout'] or r['checkin']),
                        'status': r['status'],
                        'url': f"/bookings/resort",
                        'color': '#22c55e' if r['status'] == 'Confirmed' else '#f59e0b'
                    })
            except:
                continue
        
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
@admin_required
def api_stats():
    """Get current stats"""
    return jsonify(get_stats())

# ============== STATIC FILES ==============

@app.route('/uploads/<path:filename>')
def uploads(filename):
    """Serve uploaded files"""
    return send_from_directory(UPLOAD_FOLDER, filename)

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    flash('Page not found', 'error')
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def server_error(e):
    flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=ADMIN_PORT)
