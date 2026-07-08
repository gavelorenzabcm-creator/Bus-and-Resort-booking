"""
Unified Launcher - Starts both main website and admin panel
"""
import os
import sys
import subprocess
import time
import signal
from threading import Thread

# Ensure paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

processes = []

def start_server(name, module, port):
    """Start a Flask server"""
    print(f"Starting {name} on port {port}...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    escaped_base_dir = base_dir.replace("\\", "\\\\")
    env = os.environ.copy()
    env['FLASK_PORT'] = str(port)
    env['PYTHONPATH'] = base_dir
    
    proc = subprocess.Popen(
        [sys.executable, '-c', f'''
import sys
sys.path.insert(0, "{escaped_base_dir}")
from {module} import app
app.run(host="0.0.0.0", port={port}, debug=False, threaded=True)
        '''],
        env=env,
    )
    
    processes.append((name, proc))
    return proc

def check_server(url, max_attempts=30):
    """Check if server is ready"""
    import urllib.request
    for i in range(max_attempts):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except:
            time.sleep(0.5)
    return False

def shutdown(signum=None, frame=None):
    """Graceful shutdown"""
    print("\nShutting down servers...")
    for name, proc in processes:
        print(f"  Stopping {name}...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    print("All servers stopped")
    sys.exit(0)

def main():
    """Main entry point"""
    print("="*60)
    print("BusResort Booking System")
    print("="*60)
    
# Initialize database before starting servers
    print("Initializing database...")
    try:
        from shared.db import init_db, get_db_connection, migrate_cms_schema
        init_db()
        # Ensure WebsiteSettings table exists
        try:
            conn = get_db_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS WebsiteSettings (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    site_name VARCHAR(255) DEFAULT 'BusResort',
                    homepage_welcome TEXT DEFAULT 'Welcome to BusResort',
                    homepage_description TEXT DEFAULT 'Book Mini Bus rentals and cozy resort stays seamlessly.',
                    contact_email VARCHAR(255) DEFAULT '',
                    homepage_image TEXT DEFAULT '',
                    resort_image TEXT DEFAULT '',
                    bus_image TEXT DEFAULT ''
                )
            """)
            conn.execute("INSERT OR IGNORE INTO WebsiteSettings (id) VALUES (1)")
            migrate_cms_schema(conn)
            conn.commit()
            conn.close()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Warning: Database init issue: {e}")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    try:
        # Start servers
        main_proc = start_server("Main Website", "main_site.app", 5000)
        admin_proc = start_server("Admin Panel", "admin_site.admin_app", 5001)
        
        # Wait for servers to be ready
        print("\nWaiting for servers...")
        
        main_ready = check_server("http://localhost:5000")
        admin_ready = check_server("http://localhost:5001")
        
        if main_ready and admin_ready:
            print("\n" + "="*60)
            print("SYSTEM READY")
            print("="*60)
            print("\nMain Website: http://localhost:5000")
            print("Admin Panel:  http://localhost:5001")
            print("   Login: admin / admin123")
            print("\nPress Ctrl+C to stop")
            print("="*60 + "\n")
            
            # Monitor processes
            while True:
                for name, proc in processes:
                    if proc.poll() is not None:
                        print(f"\n{name} crashed! Restarting...")
                        # Could add restart logic here
                        shutdown()
                        return
                time.sleep(2)
        else:
            print("\nFailed to start servers")
            shutdown()
            
    except Exception as e:
        print(f"\nError: {e}")
        shutdown()

if __name__ == '__main__':
    main()
