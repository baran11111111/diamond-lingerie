import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = 'diamond_secret_key_gold'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

DB_PATH = 'database.db'

def currency_format_func(value):
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return value

app.jinja_env.filters['currency'] = currency_format_func

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
    if 'user_id' in session: return redirect(url_for('dashboard'))
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
        flash('Geçersiz kullanıcı adı veya şifre.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    category_filter = request.args.get('category')
    conn = get_db_connection()
    if category_filter:
        products = conn.execute('SELECT * FROM products WHERE category = ?', (category_filter,)).fetchall()
    else:
        products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('dashboard.html', products=products, active_category=category_filter)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_product':
            # Ürün ekleme mantığı...
            pass
    products = conn.execute('SELECT * FROM products').fetchall()
    users = conn.execute('SELECT * FROM users WHERE is_admin = 0').fetchall()
    conn.close()
    return render_template('admin.html', products=products, users=users)

@app.route('/cart')
def cart():
    if 'user_id' not in session: return redirect(url_for('login'))
    cart_items = []
    subtotal = 0
    total_series = 0
    conn = get_db_connection()
    
    # Hata veren kısım burasıydı, düzelttim:
    current_cart = session.get('cart', {})
    for pid, quantity in current_cart.items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        if product:
            s_price = product['unit_price'] * product['series_count']
            i_total = s_price * quantity
            cart_items.append({'product': product, 'quantity': quantity, 'series_price': s_price, 'item_total': i_total})
            subtotal += i_total
            total_series += quantity
    conn.close()

    # İndirim hesaplama
    discount_percent = 20 if total_series >= 25 else (10 if total_series >= 10 else 0)
    discount_amount = subtotal * (discount_percent / 100)
    total = subtotal - discount_amount

    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, 
                           discount_percent=discount_percent, discount_amount=discount_amount, 
                           total=total, total_series=total_series)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    cart = session.get('cart', {})
    quantity = int(request.form.get('quantity', 1))
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + quantity
    session['cart'] = cart
    session.modified = True
    flash('Ürün sepete eklendi.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/checkout')
def checkout():
    if 'user_id' not in session: return redirect(url_for('login'))
    # Ödeme sayfası hesaplamalarını tekrar yap
    return render_template('checkout.html', total=0, subtotal=0, discount_amount=0) # Şimdilik basit tutalım

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    for key, val in request.form.items():
        if key.startswith('qty_'):
            pid = key.split('_')[1]
            try:
                q = int(val)
                if q > 0: cart[pid] = q
                else: cart.pop(pid, None)
            except: pass
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

@app.route('/place_order', methods=['POST'])
def place_order():
    session.pop('cart', None)
    flash('Siparişiniz başarıyla alındı!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)