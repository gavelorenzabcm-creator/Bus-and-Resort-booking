"""
Data Models - Simple data classes for the application
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class Booking:
    """Base booking model"""
    id: int
    name: str
    email: str
    contact: str
    status: str
    price: float
    created_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'contact': self.contact,
            'status': self.status,
            'price': self.price
        }

@dataclass
class BusBooking(Booking):
    """Bus booking model"""
    pickup: str = ''
    destination: str = ''
    datetime: str = ''
    
    @classmethod
    def from_row(cls, row):
        """Create from database row"""
        return cls(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            contact=row['contact'],
            status=row['status'],
            price=float(row['price'] or 0),
            pickup=row.get('pickup', ''),
            destination=row.get('destination', ''),
            datetime=row.get('datetime', '')
        )

@dataclass
class ResortBooking(Booking):
    """Resort booking model"""
    checkin: str = ''
    checkout: str = ''
    room_type: str = ''
    guests: int = 1
    
    @classmethod
    def from_row(cls, row):
        """Create from database row"""
        return cls(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            contact=row['contact'],
            status=row['status'],
            price=float(row['price'] or 0),
            checkin=row.get('checkin', ''),
            checkout=row.get('checkout', ''),
            room_type=row.get('room_type', ''),
            guests=row.get('guests', 1)
        )

@dataclass
class Room:
    """Room model"""
    id: int
    room_type: str
    price_per_night: float
    capacity: int
    image_path: Optional[str] = None
    is_available: bool = True

@dataclass
class Notification:
    """Notification model"""
    id: int
    message: str
    type: str
    is_read: bool
    created_at: str
    
    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at
        }

@dataclass
class WebsiteSettings:
    """Website settings model"""
    site_name: str = 'BusResort'
    homepage_welcome: str = ''
    homepage_description: str = ''
    contact_email: str = ''
    homepage_image: Optional[str] = None
    resort_image: Optional[str] = None
    bus_image: Optional[str] = None
    
    @classmethod
    def from_row(cls, row):
        """Create from database row"""
        if not row:
            return cls()
        return cls(
            site_name=row.get('site_name', 'BusResort'),
            homepage_welcome=row.get('homepage_welcome', ''),
            homepage_description=row.get('homepage_description', ''),
            contact_email=row.get('contact_email', ''),
            homepage_image=row.get('homepage_image'),
            resort_image=row.get('resort_image'),
            bus_image=row.get('bus_image')
        )
