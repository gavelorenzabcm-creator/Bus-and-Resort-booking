"""
Main Website Routes - Clean and simple public-facing routes
"""
import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import UPLOAD_FOLDER, MAIN_PORT
from database import Database, get_settings
from models import WebsiteSettings, BusBooking, ResortBooking
from backend.utils import save_upload, format_price, calculate_nights, parse_date

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# Context processor
@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    try:
        row = get_settings()
        return {'settings': WebsiteSettings.from_row(row)}
    except:
        return {'settings': WebsiteSettings()}

# ============== PUBLIC PAGES ==============

@app.route('/')
def home():
    """Homepage"""
    settings = get_settings()
    return render_template('index.html', settings=WebsiteSettings.from_row(settings))

@app.route('/bus')
def bus_page():
    """Bus booking page"""
    # Get pricing
    pricing = Database.fetch_all("SELECT * FROM BusPricing ORDER BY vehicle_type")
    return render_template('bus.html', pricing=pricing)

@app.route('/resort')
def resort_page():
    """Resort booking page"""
    # Get rooms and pricing
    rooms = Database.fetch_all("SELECT * FROM ResortRooms WHERE is_available = 1")
    pricing = Database.fetch_all("SELECT * FROM RoomPricing")
    
    return render_template('resort.html', 
                         rooms=rooms,
                         pricing={p['room_type']: float(p['price_per_night']) for p in pricing})

# ============== BOOKING SUBMISSION ==============

@app.route('/book/bus', methods=['POST'])
def book_bus():
    """Submit bus booking"""
    try:
        data = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'contact': request.form.get('contact', '').strip(),
            'pickup': request.form.get('pickup', '').strip(),
            'destination': request.form.get('destination', '').strip(),
            'datetime': request.form.get('datetime', '').strip(),
            'passengers': int(request.form.get('passengers', 1)),
            'vehicle_type': request.form.get('vehicle_type', 'Standard'),
            'status': 'Pending',
            'price': float(request.form.get('price', 0)),
            'created_at': datetime.now().isoformat()
        }
        
        # Validate
        if not all([data['name'], data['email'], data['contact'], data['pickup'], data['destination']]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('bus_page'))
        
        # Save booking
        booking_id = Database.insert('BusBookings', data)
        
        flash('Booking submitted successfully! We will contact you shortly.', 'success')
        return redirect(url_for('success_page', type='bus', id=booking_id))
        
    except Exception as e:
        flash(f'Error submitting booking: {str(e)}', 'error')
        return redirect(url_for('bus_page'))

@app.route('/book/resort', methods=['POST'])
def book_resort():
    """Submit resort booking"""
    try:
        checkin = request.form.get('checkin', '').strip()
        checkout = request.form.get('checkout', '').strip()
        
        data = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'contact': request.form.get('contact', '').strip(),
            'checkin': checkin,
            'checkout': checkout,
            'guests': int(request.form.get('guests', 1)),
            'room_type': request.form.get('room_type', 'Standard'),
            'special_requests': request.form.get('special_requests', '').strip(),
            'status': 'Pending',
            'price': float(request.form.get('price', 0)),
            'created_at': datetime.now().isoformat()
        }
        
        # Validate
        if not all([data['name'], data['email'], data['contact'], checkin, checkout]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('resort_page'))
        
        # Calculate nights
        nights = calculate_nights(checkin, checkout)
        if nights < 1:
            flash('Invalid date range', 'error')
            return redirect(url_for('resort_page'))
        
        # Save booking
        booking_id = Database.insert('ResortBookings', data)
        
        flash('Booking submitted successfully! We will contact you shortly.', 'success')
        return redirect(url_for('success_page', type='resort', id=booking_id))
        
    except Exception as e:
        flash(f'Error submitting booking: {str(e)}', 'error')
        return redirect(url_for('resort_page'))

# ============== UTILITY PAGES ==============

@app.route('/success')
def success_page():
    """Booking success page"""
    booking_type = request.args.get('type')
    booking_id = request.args.get('id')
    return render_template('success.html', type=booking_type, id=booking_id)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page"""
    if request.method == 'POST':
        # Handle contact form
        flash('Message sent! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

# ============== API ENDPOINTS ==============

@app.route('/api/check-availability', methods=['POST'])
def check_availability():
    """Check room availability for dates"""
    try:
        checkin = request.json.get('checkin')
        checkout = request.json.get('checkout')
        
        if not checkin or not checkout:
            return jsonify({'error': 'Dates required'}), 400
        
        # Get available rooms
        rooms = Database.fetch_all(
            """SELECT * FROM ResortRooms 
               WHERE is_available = 1 
               AND id NOT IN (
                   SELECT room_id FROM ResortBookings 
                   WHERE status IN ('Confirmed', 'Pending')
                   AND (checkin <= ? AND checkout >= ?)
               )""",
            (checkout, checkin)
        )
        
        return jsonify({'available': len(rooms) > 0, 'rooms': rooms})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-price', methods=['POST'])
def get_price():
    """Calculate price for booking"""
    try:
        booking_type = request.json.get('type')
        
        if booking_type == 'bus':
            vehicle_type = request.json.get('vehicle_type', 'Standard')
            pricing = Database.fetch_one(
                "SELECT price FROM BusPricing WHERE vehicle_type = ?",
                (vehicle_type,)
            )
            return jsonify({'price': float(pricing['price']) if pricing else 0})
        
        elif booking_type == 'resort':
            room_type = request.json.get('room_type', 'Standard')
            checkin = request.json.get('checkin')
            checkout = request.json.get('checkout')
            
            pricing = Database.fetch_one(
                "SELECT price_per_night FROM RoomPricing WHERE room_type = ?",
                (room_type,)
            )
            
            nights = calculate_nights(checkin, checkout)
            price_per_night = float(pricing['price_per_night']) if pricing else 0
            
            return jsonify({
                'price_per_night': price_per_night,
                'nights': nights,
                'total': price_per_night * nights
            })
        
        return jsonify({'error': 'Invalid type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============== STATIC FILES ==============

@app.route('/uploads/<path:filename>')
def uploads(filename):
    """Serve uploaded files"""
    return send_from_directory(UPLOAD_FOLDER, filename)

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    flash('Something went wrong. Please try again.', 'error')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=MAIN_PORT)
