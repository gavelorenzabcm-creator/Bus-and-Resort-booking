"""
Backend Utilities - Shared helper functions
"""
import os
import re
from datetime import datetime, timedelta
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_obj, prefix=''):
    """Save uploaded file and return path"""
    if not file_obj or not file_obj.filename:
        return None
    
    if not allowed_file(file_obj.filename):
        raise ValueError(f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Generate unique filename
    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    unique_name = f"{prefix}_{timestamp}_{timestamp[-4:]}_{file_obj.filename[:10].replace(' ', '_')}"
    unique_name = re.sub(r'[^\w\-_\.]', '', unique_name)
    unique_name = f"{unique_name}.{ext}"
    
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Save file
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    file_obj.save(filepath)
    
    return f"/uploads/{unique_name}"

def delete_upload(filepath):
    """Delete uploaded file"""
    if not filepath:
        return
    
    try:
        filename = os.path.basename(filepath)
        full_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        print(f"Warning: Could not delete file {filepath}: {e}")

def format_price(amount):
    """Format price with commas and 2 decimals"""
    return f"{amount:,.2f}"

def parse_date(date_str):
    """Parse date string safely"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except:
        return None

def format_datetime(dt):
    """Format datetime for display"""
    if not dt:
        return ''
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d %H:%M')

def generate_booking_id():
    """Generate unique booking reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"BR{timestamp}"

def validate_email(email):
    """Simple email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def sanitize_input(text):
    """Clean user input"""
    if not text:
        return ''
    # Remove dangerous characters but keep normal text
    return re.sub(r'[<>"\']', '', str(text).strip())

def calculate_nights(checkin, checkout):
    """Calculate number of nights between dates"""
    try:
        start = parse_date(checkin)
        end = parse_date(checkout)
        if start and end:
            return max(1, (end - start).days)
    except:
        pass
    return 1
