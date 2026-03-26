import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from urllib.parse import quote

app = Flask(__name__)
# Güvenlik için secret_key'i sabit tutuyoruz
app.secret_key = 'diamond_secret_key_gold'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

DB_PATH = 'database.db'

# Para birimi formatı (1.250,00 TL formatı için)
def currency_format_func(value):
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return value

app.jinja_env.filters['currency'] = currency_format_func

# Sepet sayısını her sayfada gösteren yardımcı fonksiyon
@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    count = sum(cart.values()) if isinstance(cart, dict) else 0
    return dict(cart_count=count)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            return redirect(url_for('dashboard'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    category_filter = request.args.get('category')
    conn = get_db_connection()
    
    if category_filter:
        products = conn.execute('SELECT * FROM products WHERE category = ?', (category_filter,)).fetchall()
    else:
        products = conn.execute('SELECT * FROM products').fetchall()
        
    conn.close()
    return render_template('dashboard.html', products=products, active_category=category_filter)

# --- KRİTİK GÜVENLİK GÜNCELLEMESİ: ADMİN KİLİDİ ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # KİLİT: Giriş yapılmamışsa veya kullanıcı admin değilse dashboard'a at
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Bu sayfaya erişim yetkiniz yok. Lütfen admin hesabı ile giriş yapın.', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_product':
            # Ürün ekleme işlemleri...
            code = request.form['code']
            name = request.form['name']
            unit_price = float(request.form['unit_price'])
            series_count = int(request.form['series_count'])
            series = request.form['series']
            category = request.form['category']
            description = request.form['description']
            
            images = request.files.getlist('images[]')
            main_image_url = None
            extra_images = []
            
            if images and images[0].filename != '':
                for index, file in enumerate(images):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    url = 'uploads/' + filename
                    if index == 0: main_image_url = url
                    else: extra_images.append(url)
            
            cursor = conn.cursor()
            cursor.execute('INSERT INTO products (code, name, unit_price, series_count, series, category, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                           (code, name, unit_price, series_count, series, category, description, main_image_url))
            product_id = cursor.lastrowid
            for ext in extra_images:
                cursor.execute('INSERT INTO product_images (product_id, image_url) VALUES (?, ?)', (product_id, ext))
            conn.commit()
            flash('Ürün başarıyla eklendi.', 'success')

        elif action == 'add_user':
            username = request.form['username']
            password = request.form['password']
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            try:
                conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)', (username, password_hash, False))
                conn.commit()
                flash('Yeni bayi hesabı oluşturuldu.', 'success')
            except sqlite3.IntegrityError:
                flash('Bu kullanıcı adı zaten mevcut.', 'error')

    products = conn.execute('SELECT * FROM products').fetchall()
    users = conn.execute('SELECT * FROM users WHERE is_admin = 0').fetchall()
    conn.close()
    return render_template('admin.html', products=products, users=users)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    gallery = conn.execute('SELECT * FROM product_images WHERE product_id = ?', (product_id,)).fetchall()
    conn.close()
    return render_template('product_detail.html', product=product, gallery=gallery)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    if 'cart' not in session: session['cart'] = {}
    
    quantity = int(request.form.get('quantity', 1))
    pid = str(product_id)
    session['cart'][pid] = session['cart'].get(pid, 0) + quantity
    session.modified = True
    flash('Ürün sepete eklendi.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/cart')
def cart():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cart_items = []
    subtotal = 0
    total_series = 0
    
    for pid, quantity in session.get('cart', {}).items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        if product:
            item_total = (product['unit_price'] * product['series_count']) * quantity
            cart_items.append({'product': product, 'quantity': quantity, 'item_total': item_total})
            subtotal += item_total
            total_series += quantity
    conn.close()

    discount_amount = 0
    if total_series >= 25: discount_amount = subtotal * 0.20
    elif total_series >= 10: discount_amount = subtotal * 0.10
    
    total = subtotal - discount_amount
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, discount_amount=discount_amount, total=total)

@app.route('/checkout')
def checkout():
    if 'user_id' not in session or not session.get('cart'):
        return redirect(url_for('cart'))
    
    conn = get_db_connection()
    subtotal = 0
    total_series = 0
    for pid, quantity in session['cart'].items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        if product:
            subtotal += (product['unit_price'] * product['series_count']) * quantity
            total_series += quantity
    conn.close()

    discount_amount = subtotal * 0.20 if total_series >= 25 else (subtotal * 0.10 if total_series >= 10 else 0)
    total = subtotal - discount_amount
    
    return render_template('checkout.html', subtotal=subtotal, discount_amount=discount_amount, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    payment_method = request.form.get('payment_method', 'Havale/EFT')
    session.pop('cart', None) # Sipariş tamamlanınca sepeti temizle
    flash(f'Siparişiniz kaydedildi. Ödeme Yöntemi: {payment_method}', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)