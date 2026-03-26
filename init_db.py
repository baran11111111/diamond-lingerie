import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = 'database.db'

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )
    ''')

    # Create products table
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            series_count INTEGER NOT NULL,
            series TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            image_url TEXT NOT NULL
        )
    ''')

    # Create product_images table for the gallery
    cursor.execute('''
        CREATE TABLE product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')

    # Create orders table
    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_price REAL NOT NULL,
            discount_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT DEFAULT 'Yeni sipariş',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create order_items table
    cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            series_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')

    # Insert default admin
    admin_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
    cursor.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)', ('admin', admin_hash, True))

    # Insert default reseller
    reseller_hash = generate_password_hash('bayi123', method='pbkdf2:sha256')
    cursor.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)', ('bayi', reseller_hash, False))

    # Insert sample products
    products = [
        ('2601', 'Lace Bralette Black', 450.00, 4, 'Seri: S-M-L-XL', 'SEDUCTION FANTASY', 'Modern kesim, lüks dantel detaylı siyah bralette. Esnek ve konforlu yapısıyla yüksek kalite standartlarında üretilmiştir.', 'https://images.unsplash.com/photo-1599022416248-1854bb62657d?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60'),
        ('2602', 'Silk Nightgown Gold', 1200.00, 4, 'Seri: S-M-L-XL', 'DIAMOND', 'Saf ipekten üretilmiş, altın rengi uzun gecelik. Zarif askıları ve premium dokusu ile üst düzey bir deneyim sunar.', 'https://images.unsplash.com/photo-1616149495039-2a9c4059ce36?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60'),
        ('2603', 'Premium Satin Robe White', 850.00, 3, 'Seri: M-L-XL', 'COLLECTION', 'Beyaz saten sabahlık, yumuşak dokusu ve şık tasarımıyla dikkat çeker. Ev içi giyimde lüksü arayanlar için tasarlandı.', 'https://images.unsplash.com/photo-1583307567786-077b9ce0c9fc?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60')
    ]
    for p in products:
        cursor.execute('INSERT INTO products (code, name, unit_price, series_count, series, category, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', p)
        product_id = cursor.lastrowid
        # Add sample gallery images for each product
        cursor.execute('INSERT INTO product_images (product_id, image_url) VALUES (?, ?)', (product_id, 'https://images.unsplash.com/photo-1516257984-b1b4d707412e?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60'))
        cursor.execute('INSERT INTO product_images (product_id, image_url) VALUES (?, ?)', (product_id, 'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60'))

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
