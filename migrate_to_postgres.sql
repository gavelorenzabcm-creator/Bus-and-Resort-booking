-- PostgreSQL migration generated from bookings.db
-- Execute this against your Supabase database (e.g., via psql or Supabase SQL Editor)

BEGIN;

CREATE TABLE Admin (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255) DEFAULT '',
            email_enabled INTEGER DEFAULT 0
        );

CREATE TABLE BusBookings (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            pickup VARCHAR(255),
            destination VARCHAR(255) NOT NULL,
            datetime TIMESTAMP NOT NULL,
            checkin TIMESTAMP,
            checkout TIMESTAMP NOT NULL,
            passengers INTEGER DEFAULT 1,
            price REAL DEFAULT 0,
            status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE BusPricing (
            id SERIAL PRIMARY KEY,
            destination VARCHAR(255) UNIQUE NOT NULL,
            price REAL DEFAULT 0
        );

CREATE TABLE CMS_BrandingAssets (
            id SERIAL PRIMARY KEY,
            primary_color TEXT DEFAULT '#2563EB',
            secondary_color TEXT DEFAULT '#16A34A',
            accent_color TEXT DEFAULT '#F59E0B',
            site_logo_path TEXT DEFAULT '',
            favicon_path TEXT DEFAULT '',
            default_button_colors TEXT DEFAULT 'blue'
        );

CREATE TABLE CMS_BusCatalog (
            id SERIAL PRIMARY KEY,
            sort_order INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            image_path TEXT DEFAULT '',
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            features_json TEXT DEFAULT '[]'
        );

CREATE TABLE CMS_ContactInfo (
            id SERIAL PRIMARY KEY,
            phone TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            email TEXT DEFAULT '',
            office_address TEXT DEFAULT '',
            google_maps_link TEXT DEFAULT '',
            business_hours TEXT DEFAULT ''
        , business_name TEXT DEFAULT '', business_tagline TEXT DEFAULT '', secondary_phone TEXT DEFAULT '', whatsapp_number TEXT DEFAULT '', facebook_url TEXT DEFAULT '', instagram_url TEXT DEFAULT '', x_url TEXT DEFAULT '', tiktok_url TEXT DEFAULT '', youtube_url TEXT DEFAULT '');

CREATE TABLE CMS_FeatureCards (
            id SERIAL PRIMARY KEY,
            card_order INTEGER DEFAULT 0,
            icon_class TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT ''
        );

CREATE TABLE CMS_FooterContent (
            id SERIAL PRIMARY KEY,
            footer_logo_path TEXT DEFAULT '',
            footer_description TEXT DEFAULT '',
            quick_links_json TEXT DEFAULT '[]',
            copyright_text TEXT DEFAULT '',
            privacy_policy_href TEXT DEFAULT '',
            terms_href TEXT DEFAULT ''
        , contact_section_title TEXT DEFAULT '');

CREATE TABLE CMS_GalleryImages (
            id SERIAL PRIMARY KEY,
            image_order INTEGER DEFAULT 0,
            image_path TEXT DEFAULT '',
            caption TEXT DEFAULT ''
        );

CREATE TABLE CMS_HeroButtons (
            id SERIAL PRIMARY KEY,
            button_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            text TEXT DEFAULT '',
            href TEXT DEFAULT '#',
            color TEXT DEFAULT 'blue'
        );

CREATE TABLE CMS_HeroSlides (
            id SERIAL PRIMARY KEY,
            slide_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            background_image_path TEXT DEFAULT '',
            carousel_image_path TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT ''
        );

CREATE TABLE CMS_Homepage (
            id SERIAL PRIMARY KEY,
            website_title TEXT DEFAULT '',
            hero_title TEXT DEFAULT '',
            hero_subtitle TEXT DEFAULT '',
            booking_section_title TEXT DEFAULT '',
            booking_description TEXT DEFAULT '',
            booking_placeholder_full_name TEXT DEFAULT '',
            booking_placeholder_phone TEXT DEFAULT '',
            booking_button_text TEXT DEFAULT '',
            search_labels TEXT DEFAULT '',
            booking_success_message TEXT DEFAULT '',
            booking_error_message TEXT DEFAULT ''
        , booking_success_popup_title TEXT DEFAULT 'Booking Submitted Successfully!', booking_success_popup_message TEXT DEFAULT 'Thank you for choosing BusResort!\nYour booking has been successfully submitted and is now awaiting confirmation from our administrator. We appreciate your trust in our service and look forward to serving you. Please keep your booking reference number for future inquiries.', booking_success_popup_ok_text TEXT DEFAULT 'OK', booking_success_popup_view_text TEXT DEFAULT 'View My Booking', booking_success_popup_show_icon INTEGER DEFAULT 1);

CREATE TABLE CMS_NavMenuItems (
            id SERIAL PRIMARY KEY,
            item_order INTEGER DEFAULT 0,
            is_visible INTEGER DEFAULT 1,
            name TEXT DEFAULT '',
            href TEXT DEFAULT '#'
        );

CREATE TABLE CMS_ResortCatalog (
            id SERIAL PRIMARY KEY,
            sort_order INTEGER DEFAULT 0,
            promo_text TEXT DEFAULT '',
            resort_image_path TEXT DEFAULT '',
            room_image_path TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1
        );

CREATE TABLE CMS_ResortRooms (
            id SERIAL PRIMARY KEY,
            sort_order INTEGER DEFAULT 0,
            resort_room_name TEXT DEFAULT '',
            room_type TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            amenities_json TEXT DEFAULT '[]',
            capacity INTEGER DEFAULT 1,
            is_available INTEGER DEFAULT 1
        );

CREATE TABLE CMS_SocialLinks (
            id SERIAL PRIMARY KEY,
            platform TEXT DEFAULT '',
            href TEXT DEFAULT '',
            is_visible INTEGER DEFAULT 1,
            link_order INTEGER DEFAULT 0
        );

CREATE TABLE CMS_Testimonials (
            id SERIAL PRIMARY KEY,
            card_order INTEGER DEFAULT 0,
            customer_name TEXT DEFAULT '',
            customer_photo_path TEXT DEFAULT '',
            rating INTEGER DEFAULT 5,
            review TEXT DEFAULT ''
        );

CREATE TABLE CancellationLog (
            id SERIAL PRIMARY KEY,
            booking_type VARCHAR(20) NOT NULL,
            booking_id INTEGER NOT NULL,
            customer_name VARCHAR(255),
            travel_date VARCHAR(10),
            cancelled_by VARCHAR(20) NOT NULL,
            reason TEXT,
            date_cancelled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE CancelledBusBookings (
            id SERIAL PRIMARY KEY,
            booking_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            pickup VARCHAR(255),
            destination VARCHAR(255) NOT NULL,
            datetime TIMESTAMP NOT NULL,
            checkin TIMESTAMP,
            checkout TIMESTAMP NOT NULL,
            passengers INTEGER,
            price REAL,
            created_at TIMESTAMP,
            cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cancelled_by VARCHAR(20) NOT NULL,
            UNIQUE(booking_id)
        );

CREATE TABLE CancelledResortBookings (
            id SERIAL PRIMARY KEY,
            booking_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            checkin DATE NOT NULL,
            checkout DATE NOT NULL,
            checkin_time VARCHAR(5),
            checkout_time VARCHAR(5),
            guests INTEGER,
            room_type TEXT,
            payment_method VARCHAR(20),
            status VARCHAR(20),
            price_per_night REAL,
            total_cost REAL,
            price REAL,
            is_exclusive INTEGER,
            exclusive_price REAL,
            appliances_json TEXT,
            appliances_cost REAL,
            room_instances TEXT,
            created_at TIMESTAMP,
            cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cancelled_by VARCHAR(20) NOT NULL,
            UNIQUE(booking_id)
        );

CREATE TABLE Feedback (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            service_type VARCHAR(50) NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >=1 AND rating <=5),
            comment TEXT NOT NULL,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE Notification (
            id SERIAL PRIMARY KEY,
            message TEXT NOT NULL,
            type VARCHAR(50) NOT NULL CHECK(type IN ('booking_bus', 'booking_resort', 'review', 'cancel_bus', 'cancel_resort')),
            is_read INTEGER DEFAULT 0,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE RentableAppliances (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            price REAL DEFAULT 0
        );

CREATE TABLE ResortBookings (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            checkin DATE NOT NULL,
            checkout DATE NOT NULL,
            checkin_time VARCHAR(5) DEFAULT '14:00',
            checkout_time VARCHAR(5) DEFAULT '12:00',
            guests INTEGER DEFAULT 1,
            room_type TEXT,
            payment_method VARCHAR(20) DEFAULT 'Cash',
            status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
            price_per_night REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            price REAL DEFAULT 0,
            is_exclusive INTEGER DEFAULT 0,
            exclusive_price REAL DEFAULT 0,
            appliances_json TEXT,
            appliances_cost REAL DEFAULT 0,
            room_instances TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE ResortOptions (
            id SERIAL PRIMARY KEY CHECK (id = 1),
            exclusive_price REAL DEFAULT 0
        );

CREATE TABLE ResortRooms (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            room_type VARCHAR(100) NOT NULL,
            capacity INTEGER DEFAULT 2,
            status VARCHAR(20) DEFAULT 'Available' CHECK(status IN ('Available', 'Unavailable')),
            image_path TEXT
        );

CREATE TABLE ResortRoomPhotos (
            id SERIAL PRIMARY KEY,
            room_id INTEGER NOT NULL,
            photo_order INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            UNIQUE(room_id, photo_order),
            FOREIGN KEY(room_id) REFERENCES ResortRooms(id) ON DELETE CASCADE
        );

CREATE TABLE RoomPricing (
            id SERIAL PRIMARY KEY,
            room_type VARCHAR(100) UNIQUE NOT NULL,
            price_per_night REAL DEFAULT 0
        );

CREATE TABLE WebsiteSettings (
            id SERIAL PRIMARY KEY,
            site_name VARCHAR(255) DEFAULT 'BusResort',
            homepage_welcome TEXT DEFAULT 'Welcome to BusResort',
            homepage_description TEXT DEFAULT 'Book Mini Bus rentals and cozy resort stays seamlessly.',
            contact_email VARCHAR(255) DEFAULT '',
            contact_phone VARCHAR(50) DEFAULT '',
            logo TEXT DEFAULT '',
            homepage_image TEXT DEFAULT '',
            resort_image TEXT DEFAULT '',
            bus_image TEXT DEFAULT ''
        );

INSERT INTO WebsiteSettings (id, site_name, homepage_welcome, homepage_description, contact_email, contact_phone, logo, homepage_image, resort_image, bus_image) VALUES (1, 'BusResort', 'Welcome', 'WELCOME', 'api@example.com', '', '', 'uploads/homepage_20260704184616625300_main.jpg', 'uploads/resort_20260501215556479121_MBR.jpg', 'uploads/bus_20260704184616626513_bus.jpg') ON CONFLICT (id) DO NOTHING;

INSERT INTO CMS_ContactInfo (id, phone, mobile, email, office_address, google_maps_link, business_hours, business_name, business_tagline, secondary_phone, whatsapp_number, facebook_url, instagram_url, x_url, tiktok_url, youtube_url) VALUES (1, '', '+63 900 111 2222', 'My-contact@example.com', '', 'https://l.facebook.com/l.php?u=https%3A%2F%2Fwww.bing.com%2Fmaps%2Fdefault.aspx%3Fv%3D2%26pc%3DFACEBK%26mid%3D8100%26where1%3DBrgy.%2520Lago%252C%2520Glan%252C%2520Philippines%252C%25209517%26FORM%3DFBKPL1%26mkt%3Den-US%26fbclid%3DIwZXh0bgNhZW0CMTAAYnJpZBExWWFpblZFWUZobGZxN0NSaXNydGMGYXBwX2lkEDIyMjAzOTE3ODgyMDA4OTIAAR7nKpuBiYLqmcnGwRHm96RO7TeKBJEksvRm_jiBCOcTY4rf39iOBjh-yzdJWA_aem_1DGjmUqqZZijAaDlDpWZ8A&h=AUCR9408_kF3jejYlie6h3KgWO8S2heacjqzFxJhkac8rNbPgTmE0wg4IdcRCrybcPaEqlc7IM0XI4tIKi_uDUpmLBbtMe3p7LfIfQO2Z3Z8osz0u9JYpogl0E62itIfr_Tz', '', 'BusResort', 'Enjoy!!!!', '', '', 'https://www.facebook.com/macayabeachresort', '', '', '', '') ON CONFLICT (id) DO NOTHING;

INSERT INTO CMS_FooterContent (id, footer_logo_path, footer_description, quick_links_json, copyright_text, privacy_policy_href, terms_href, contact_section_title) VALUES (1, '', 'MACAYA BUSRESORT BOOKINGS', '[]', '2026 API', '', 'https://example.com/t-api', 'Contact API') ON CONFLICT (id) DO NOTHING;

INSERT INTO CMS_Homepage (id, website_title, hero_title, hero_subtitle, booking_section_title, booking_description, booking_placeholder_full_name, booking_placeholder_phone, booking_button_text, search_labels, booking_success_message, booking_error_message, booking_success_popup_title, booking_success_popup_message, booking_success_popup_ok_text, booking_success_popup_view_text, booking_success_popup_show_icon) VALUES (1, '', '', '', '', '', '', '', '', '', '', '', 'Booking Submitted Successfully!', 'Thank you for choosing BusResort!
Your booking has been successfully submitted and is now awaiting confirmation from our administrator. We appreciate your trust in our service and look forward to serving you. Please keep your booking reference number for future inquiries.', 'OK', 'View My Booking', 0) ON CONFLICT (id) DO NOTHING;

INSERT INTO CMS_BrandingAssets (id, primary_color, secondary_color, accent_color, site_logo_path, favicon_path, default_button_colors) VALUES (1, '#2563EB', '#16A34A', '#F59E0B', '', '', 'blue') ON CONFLICT (id) DO NOTHING;

INSERT INTO ResortOptions (id, exclusive_price) VALUES (1, 10000.0) ON CONFLICT (id) DO NOTHING;

INSERT INTO ResortRooms (id, name, room_type, capacity, status, image_path) VALUES (1, 'ROOM1', 'Family', 4, 'Available', '') ON CONFLICT (id) DO NOTHING;
INSERT INTO ResortRooms (id, name, room_type, capacity, status, image_path) VALUES (2, 'ROOM 2', 'Family', 4, 'Available', '') ON CONFLICT (id) DO NOTHING;

INSERT INTO ResortRoomPhotos (id, room_id, photo_order, image_path) VALUES (1, 2, 0, '/uploads/room_0_20260706223330058357_main.jpg') ON CONFLICT (id) DO NOTHING;
INSERT INTO ResortRoomPhotos (id, room_id, photo_order, image_path) VALUES (2, 2, 1, '/uploads/room_1_20260706223330098023_bus.jpg') ON CONFLICT (id) DO NOTHING;
INSERT INTO ResortRoomPhotos (id, room_id, photo_order, image_path) VALUES (3, 2, 2, '/uploads/room_2_20260706223330110831_dis_to_dis.png') ON CONFLICT (id) DO NOTHING;

INSERT INTO RentableAppliances (id, name, price) VALUES (1, 'Refrigerator', 500.0) ON CONFLICT (id) DO NOTHING;

INSERT INTO RoomPricing (id, room_type, price_per_night) VALUES (1, 'Family', 2500.0) ON CONFLICT (id) DO NOTHING;

INSERT INTO CMS_SocialLinks (id, platform, href, is_visible, link_order) VALUES (14, 'facebook', 'https://www.facebook.com/macayabeachresort', 1, 0) ON CONFLICT (id) DO NOTHING;

COMMIT;