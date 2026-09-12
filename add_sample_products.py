"""
Script to add sample electronics products to the store
Run this ONCE to seed the database with sample products
"""

from app import create_app
from models import db
from models.store import Product

app = create_app()

# Sample product data
SAMPLE_PRODUCTS = [
    {
        "name": "Arduino Uno Rev3",
        "description": "Microcontroller board based on ATmega328P. Perfect for beginners learning electronics and programming.",
        "price_inr": 2500,
        "discount_price_inr": 1999,
        "stock": 45,
        "category": "Microcontrollers",
        "brand": "Arduino",
        "sku": "ARD-UNO-001",
        "rating": 4.8,
        "is_new_arrival": True,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Raspberry Pi 4 (4GB RAM)",
        "description": "Single-board computer with quad-core processor. Great for IoT, robotics, and embedded projects.",
        "price_inr": 6500,
        "discount_price_inr": 5999,
        "stock": 28,
        "category": "Single Board Computers",
        "brand": "Raspberry Pi",
        "sku": "RPI-4GB-001",
        "rating": 4.9,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "DHT22 Temperature & Humidity Sensor",
        "description": "Digital sensor for measuring temperature and humidity. Compatible with Arduino and Raspberry Pi.",
        "price_inr": 599,
        "discount_price_inr": 499,
        "stock": 120,
        "category": "Sensors",
        "brand": "DHT",
        "sku": "DHT-22-001",
        "rating": 4.5,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Ultrasonic Distance Sensor (HC-SR04)",
        "description": "Non-contact distance measurement sensor. Ideal for robotics projects and obstacle avoidance.",
        "price_inr": 399,
        "discount_price_inr": 299,
        "stock": 85,
        "category": "Sensors",
        "brand": "Generic",
        "sku": "HC-SR04-001",
        "rating": 4.3,
        "is_new_arrival": True,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Servo Motor (9g)",
        "description": "Compact servo motor for robotics and automation. 180-degree rotation capability.",
        "price_inr": 449,
        "discount_price_inr": 349,
        "stock": 60,
        "category": "Motors",
        "brand": "TowerPro",
        "sku": "SERVO-9G-001",
        "rating": 4.6,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Jumper Wires Pack (40 pcs)",
        "description": "Set of 40 pre-soldered jumper wires for breadboard connections. Male-to-male connectors.",
        "price_inr": 199,
        "discount_price_inr": 149,
        "stock": 200,
        "category": "Connectors & Wires",
        "brand": "Generic",
        "sku": "JUMPER-40PC-001",
        "rating": 4.4,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Breadboard (830 holes)",
        "description": "Large solderless breadboard with 830 tie points. Perfect for prototyping circuits.",
        "price_inr": 349,
        "discount_price_inr": 249,
        "stock": 75,
        "category": "Breadboards",
        "brand": "Generic",
        "sku": "BB-830-001",
        "rating": 4.7,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "OLED Display Module (0.96 inch)",
        "description": "128x64 pixel OLED display with I2C interface. Bright and clear display for projects.",
        "price_inr": 899,
        "discount_price_inr": 699,
        "stock": 35,
        "category": "Displays",
        "brand": "Generic",
        "sku": "OLED-096-001",
        "rating": 4.8,
        "is_new_arrival": True,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "USB Power Supply (5V 2A)",
        "description": "Reliable USB power supply with 2A output. Perfect for Arduino and Raspberry Pi projects.",
        "price_inr": 499,
        "discount_price_inr": 399,
        "stock": 50,
        "category": "Power Supplies",
        "brand": "Generic",
        "sku": "USB-5V2A-001",
        "rating": 4.5,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "LED Assortment Kit (100 pcs)",
        "description": "Pack of 100 LEDs in various colors. Resistors included for safe operation.",
        "price_inr": 299,
        "discount_price_inr": 199,
        "stock": 40,
        "category": "Electronic Components",
        "brand": "Generic",
        "sku": "LED-100PC-001",
        "rating": 4.4,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "Motor Driver Module (L298N)",
        "description": "Dual motor driver for controlling DC motors. Supports PWM speed control.",
        "price_inr": 399,
        "discount_price_inr": 299,
        "stock": 32,
        "category": "Motor Controllers",
        "brand": "Generic",
        "sku": "L298N-001",
        "rating": 4.6,
        "is_new_arrival": False,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
    {
        "name": "GPS Module (NEO-6M)",
        "description": "UBLOX NEO-6M GPS module with UART interface. Accurate location tracking.",
        "price_inr": 1499,
        "discount_price_inr": 1199,
        "stock": 18,
        "category": "Sensors",
        "brand": "UBLOX",
        "sku": "GPS-NEO6M-001",
        "rating": 4.7,
        "is_new_arrival": True,
        "status": "published",
        "image_url": "/static/images/default_product.svg",
        "gst_percent": 18.0,
    },
]

def add_products():
    """Add sample products to database"""
    with app.app_context():
        try:
            # Check if products already exist
            existing_count = Product.query.count()
            if existing_count > 0:
                print(f"⚠️  Database already contains {existing_count} products.")
                response = input("Do you want to continue adding more? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("Cancelled.")
                    return

            added = 0
            for product_data in SAMPLE_PRODUCTS:
                # Check if product with same SKU already exists
                if Product.query.filter_by(sku=product_data["sku"]).first():
                    print(f"⏭️  Skipping {product_data['name']} (already exists)")
                    continue

                product = Product(**product_data)
                db.session.add(product)
                added += 1
                print(f"[OK] Added: {product.name}")

            db.session.commit()
            total = Product.query.count()
            print(f"\n[SUCCESS] Added {added} new products. Total in database: {total}")

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] {e}")
            raise

if __name__ == "__main__":
    print("[*] Adding sample products to database...")
    print("=" * 50)
    add_products()
    print("=" * 50)
    print("Done! Refresh your browser to see the products.")
