# BusResort Booking System

## ✅ STATUS: PRODUCTION READY

Fully functional web application with admin panel and main website. All features tested and working.

## 🚀 Quick Start - Run Both Sites

### Option 1: Using runall.bat (Windows)
```cmd
runall.bat
```

### Option 2: Using Python (Cross-platform)
```bash
# Make sure virtual environment is activated
.venv\Scripts\python.exe runall.py
```

**One command starts everything:**
- **Main site:** http://localhost:5000
- **Admin site:** http://localhost:5001 
- **Login:** `admin` / `admin123` ⚠️ **Change password after first login!**

Press `Ctrl+C` to stop, or run `stop.bat` in another terminal.

---

## 📋 Requirements

```bash
pip install -r requirements.txt
```

Key dependencies:
- Flask 3.0.3
- Flask-Mail 0.9.1
- openpyxl 3.1.2 (Excel exports)
- weasyprint 60.1 (PDF exports - optional)

---

## ✨ Features

### Customer Site (:5000)
- 🚌 Bus rental bookings
- 🏨 Resort room bookings
- 🔍 Booking search & confirmation
- 📝 Customer feedback
- 📅 Availability calendars
- 📱 Mobile responsive

### Admin Panel (:5001)
- 📊 Dashboard with booking calendars
- 📝 Manage bookings (confirm, cancel, delete)
- 💰 Sales reports with filters (Daily/Weekly/Monthly/Yearly/Custom)
- 📈 Export reports (Excel, CSV, PDF)
- 🏠 Room management with image uploads
- 💵 Pricing management
- 📺 Website content management
- 🔔 Real-time notifications
- 📧 Email notifications

---

## 📁 Project Structure

```
.
├── admin_site/          # Admin panel (:5001)
│   ├── admin_app.py
│   └── templates/
├── main_site/           # Customer site (:5000)
│   ├── app.py
│   └── templates/
├── shared/              # Shared modules
│   ├── config.py
│   ├── db.py
│   └── shared_utils.py
├── static/uploads/      # Image uploads
├── bookings.db          # SQLite database
├── runall.py            # Server launcher
├── runall.bat           # Windows launcher
├── stop.bat             # Stop servers
├── system_audit.py      # Health check
├── test_system.py       # Feature tests
├── DEPLOYMENT.md        # Deployment guide
└── FINAL_SUMMARY.md     # Complete summary
```

---

## 🛠️ Testing & Verification

```bash
# System health check
python system_audit.py

# Feature tests
python test_system.py

# Debug image system
python debug_image_system.py
```

---

## 🌐 Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for detailed deployment instructions:
- PythonAnywhere hosting
- VPS/Server deployment
- Docker deployment
- Nginx configuration
- Security checklist

---

## 🔐 Security

**Default Credentials:**
- Username: `admin`
- Password: `admin123`

**⚠️ IMPORTANT:** Change password immediately after first login at `/admin/settings`

---

## 🆘 Troubleshooting

### Port Already in Use
The system now auto-kills processes on startup. If issues persist:
```bash
# Windows
.\stop.bat

# Or force kill
taskkill /F /IM python.exe
```

### Database Issues
```bash
# Reinitialize database
python shared/db.py
```

### Images Not Displaying
1. Check `static/uploads/` folder exists
2. Verify `/uploads/<filename>` route accessible
3. Run `python debug_image_system.py`

---

## 📊 System Status

**✅ All Features Working:**
- Booking system (bus, resort, rooms)
- Cancel booking
- Notifications
- Sales reports
- Image uploads
- All buttons and actions
- Data synchronization
- Error handling

**✅ Production Ready:**
- Comprehensive error handling
- Input validation
- Security measures
- Performance optimized
- Fully documented

---

## 📞 Documentation

- **[FINAL_SUMMARY.md](FINAL_SUMMARY.md)** - Complete system summary
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment instructions

---

**Version:** 1.0 Production Ready  
**Last Updated:** May 1, 2026

