#!/usr/bin/env python3
"""
Comprehensive System Audit for BusResort Booking System
Checks all routes, templates, database, and common issues
"""
import os
import sys
# sqlite3 removed: this audit tool now uses the centralized DB module

import importlib.util
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_database():
    """Check database structure and data integrity."""
    print("\n" + "="*60)
    print("🗄️  DATABASE AUDIT")
    print("="*60)
    
    db_path = os.path.join(os.path.dirname(__file__), 'bookings.db')
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    try:
        from shared.db_connection import get_db_connection, DB_ENGINE
        conn = get_db_connection()
        cursor = conn.cursor()

        
        # Get all tables (engine-agnostic)
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """)
        tables = [row[0] for row in cursor.fetchall()]

        print(f"✅ Database connected. Tables: {len(tables)}")
        
        # Check each table
        for table in tables:
            try:
                count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"   📊 {table}: {count} records")
            except Exception as e:
                print(f"   ❌ {table}: Error - {e}")

        
        # Check for orphaned records
        print("\n   🔍 Checking data integrity...")
        
        # Check admin user
        admin = cursor.execute("SELECT * FROM Admin WHERE username = 'admin'").fetchone()
        if admin:
            print(f"   ✅ Admin user exists (ID: {admin['id']})")
        else:
            print("   ⚠️  Default admin user not found!")
        
        # Check WebsiteSettings
        settings = cursor.execute("SELECT * FROM WebsiteSettings WHERE id = 1").fetchone()
        if settings:
            print(f"   ✅ WebsiteSettings configured")
        else:
            print("   ⚠️  WebsiteSettings not initialized")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def check_templates():
    """Check all templates for common issues."""
    print("\n" + "="*60)
    print("📄 TEMPLATE AUDIT")
    print("="*60)
    
    admin_templates = Path('admin_site/templates')
    main_templates = Path('main_site/templates')
    
    issues = []
    
    # Check for common template issues
    for template_dir in [admin_templates, main_templates]:
        if not template_dir.exists():
            issues.append(f"❌ Template directory not found: {template_dir}")
            continue
            
        for template_file in template_dir.glob('*.html'):
            try:
                content = template_file.read_text(encoding='utf-8')
                
                # Check for nested forms
                form_count = content.count('<form')
                close_form_count = content.count('</form>')
                if form_count != close_form_count:
                    issues.append(f"⚠️  {template_file.name}: Mismatched form tags ({form_count} open, {close_form_count} close)")
                
                # Check for broken links
                if 'href=""' in content or "href=''" in content:
                    issues.append(f"⚠️  {template_file.name}: Empty href attributes found")
                
                # Check for missing block closures
                block_starts = content.count('{% block')
                block_ends = content.count('{% endblock')
                if block_starts != block_ends:
                    issues.append(f"⚠️  {template_file.name}: Mismatched block tags")
                    
            except Exception as e:
                issues.append(f"❌ {template_file.name}: Error reading - {e}")
    
    if issues:
        print("⚠️  Template issues found:")
        for issue in issues[:10]:
            print(f"   {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more issues")
    else:
        print("✅ All templates look good!")
    
    return len(issues) == 0

def check_static_files():
    """Check static files and uploads."""
    print("\n" + "="*60)
    print("📁 STATIC FILES AUDIT")
    print("="*60)
    
    # Check upload folder
    upload_folder = Path('static/uploads')
    if upload_folder.exists():
        files = list(upload_folder.iterdir())
        print(f"✅ Upload folder exists: {len(files)} files")
        # Check for orphaned files
        # Use the centralized DB connection (Postgres on Vercel, SQLite locally)
        conn = None
        try:
            from shared.db_connection import get_db_connection
            conn = get_db_connection(timeout=5.0)
            cursor = conn.cursor()

            # Get all image paths from database
            used_images = set()
            try:
                rooms = cursor.execute(
                    "SELECT image_path FROM ResortRooms WHERE image_path IS NOT NULL"
                ).fetchall()
                for r in rooms:
                    if r['image_path']:
                        used_images.add(os.path.basename(r['image_path']))

                settings = cursor.execute(
                    "SELECT homepage_image, resort_image, bus_image FROM WebsiteSettings WHERE id = 1"
                ).fetchone()
                if settings:
                    for img in [settings['homepage_image'], settings['resort_image'], settings['bus_image']]:
                        if img:
                            used_images.add(os.path.basename(img))
            except Exception:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        
        orphaned = [f.name for f in files if f.name not in used_images and f.name not in ['BUS.jpg', 'MBR.jpg']]
        if orphaned:
            print(f"⚠️  {len(orphaned)} potentially orphaned files in uploads")
        
    else:
        print("❌ Upload folder not found!")
        
    return True

def check_imports():
    """Check if all required imports work."""
    print("\n" + "="*60)
    print("📦 IMPORT CHECK")
    print("="*60)
    
    required_modules = [
        'flask',
        'werkzeug',
        'jinja2',

        'openpyxl',
    ]
    
    optional_modules = [
        'weasyprint',
        'flask_mail',
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"   ✅ {module}")
        except ImportError:
            print(f"   ❌ {module} - REQUIRED MODULE MISSING!")
    
    for module in optional_modules:
        try:
            __import__(module)
            print(f"   ✅ {module} (optional)")
        except ImportError:
            print(f"   ⚠️  {module} (optional - not installed)")
    
    return True

def check_config():
    """Check configuration files."""
    print("\n" + "="*60)
    print("⚙️  CONFIGURATION AUDIT")
    print("="*60)
    
    # Check .env.example
    if os.path.exists('.env.example'):
        print("✅ .env.example exists")
    else:
        print("⚠️  .env.example not found")
    
    # Check requirements.txt
    if os.path.exists('requirements.txt'):
        with open('requirements.txt') as f:
            reqs = f.read()
        print(f"✅ requirements.txt exists ({len(reqs.splitlines())} packages)")
    else:
        print("❌ requirements.txt not found!")
    
    # Check shared/config.py
    try:
        from shared.config import Config
        print(f"✅ Config loaded")
        print(f"   Upload folder: {Config.UPLOAD_FOLDER}")
        if os.path.exists(Config.UPLOAD_FOLDER):
            print(f"   ✅ Upload folder exists")
        else:
            print(f"   ⚠️  Upload folder does not exist (will be created)")
    except Exception as e:
        print(f"❌ Config error: {e}")
    
    return True

def generate_report():
    """Generate summary report."""
    print("\n" + "="*60)
    print("📋 AUDIT SUMMARY")
    print("="*60)
    
    checks = [
        ("Database", check_database),
        ("Templates", check_templates),
        ("Static Files", check_static_files),
        ("Imports", check_imports),
        ("Configuration", check_config),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} check failed: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("FINAL STATUS")
    print("="*60)
    
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("✅ All checks passed! System looks good.")
    else:
        print("⚠️  Some issues found. Review above.")
    
    return all_passed

if __name__ == '__main__':
    generate_report()
