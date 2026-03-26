import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

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
    if not cart:
        return dict(cart_count=0)
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
    
    try:
        if category_filter:
            products = conn.execute('SELECT * FROM products WHERE category = ?', (category_filter,)).fetchall()
        else:
            products = conn.execute('SELECT * FROM products').fetchall()
    except sqlite3.OperationalError:
        # Schema mismatch, recreate db
        conn.close()
        import subprocess
        subprocess.run(["python", "init_db.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
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
        flash('Bu sayfaya erişim yetkiniz yok.', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_product':
            code = request.form['code']
            name = request.form['name']
            unit_price = float(request.form['unit_price'])
            series_count = int(request.form['series_count'])
            series = request.form['series']
            category = request.form['category']
            description = request.form['description']
            
            # Handle multiple images
            images = request.files.getlist('images[]')
            if not images or images[0].filename == '':
                flash('Resim dosyası eksik.', 'error')
                return redirect(url_for('admin'))
                
            main_image_url = None
            extra_images = []
            
            for index, file in enumerate(images):
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    url = 'uploads/' + filename
                    if index == 0:
                        main_image_url = url
                    else:
                        extra_images.append(url)
            
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

@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    if not session.get('is_admin'):
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Ürün sistemden silindi.', 'success')
    return redirect(url_for('admin'))

@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if not session.get('is_admin'):
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        series = request.form['series']
        series_count = int(request.form['series_count'])
        unit_price = float(request.form['unit_price'])
        
        images = request.files.getlist('images[]')
        
        if images and images[0].filename != '':
            # new files selected
            main_image_url = None
            extra_images = []
            
            from werkzeug.utils import secure_filename
            for index, file in enumerate(images):
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    url = 'uploads/' + filename
                    if index == 0:
                        main_image_url = url
                    else:
                        extra_images.append(url)
            
            conn.execute('''
                UPDATE products 
                SET code = ?, name = ?, series = ?, series_count = ?, unit_price = ?, image_url = ?
                WHERE id = ?
            ''', (code, name, series, series_count, unit_price, main_image_url, id))
            
            conn.execute('DELETE FROM product_images WHERE product_id = ?', (id,))
            for ext in extra_images:
                conn.execute('INSERT INTO product_images (product_id, image_url) VALUES (?, ?)', (id, ext))
        else:
            conn.execute('''
                UPDATE products 
                SET code = ?, name = ?, series = ?, series_count = ?, unit_price = ?
                WHERE id = ?
            ''', (code, name, series, series_count, unit_price, id))
            
        conn.commit()
        conn.close()
        flash('Ürün bilgileri başarıyla güncellendi.', 'success')
        return redirect(url_for('admin'))
        
    conn.close()
    return render_template('admin_edit.html', p=product)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        flash('Ürün bulunamadı.', 'error')
        return redirect(url_for('dashboard'))
        
    gallery = conn.execute('SELECT * FROM product_images WHERE product_id = ?', (product_id,)).fetchall()
    conn.close()
    
    return render_template('product_detail.html', product=product, gallery=gallery)

@app.route('/add_to_cart/<int:product_id>', methods=['GET', 'POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if 'cart' not in session:
        session['cart'] = {}
        
    quantity = 1
    if request.method == 'POST':
        try:
            quantity = int(request.form.get('quantity', 1))
        except ValueError:
            quantity = 1
            
    pid = str(product_id)
    if pid in session['cart']:
        session['cart'][pid] += quantity
    else:
        session['cart'][pid] = quantity
        
    session.modified = True
    flash(f'{quantity} seri sepete eklendi.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if 'cart' not in session:
        session['cart'] = {}
        
    for key, val in request.form.items():
        if key.startswith('qty_'):
            pid = key.split('_')[1]
            try:
                q = int(val)
                if q > 0:
                    session['cart'][pid] = q
                else:
                    session['cart'].pop(pid, None)
            except ValueError:
                pass
                
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if not session.get('cart'):
        session['cart'] = {}
        session.modified = True
        
    conn = get_db_connection()
    cart_items = []
    total_series = 0
    subtotal = 0
    
    for pid, quantity in session['cart'].items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        if product:
            series_price = product['unit_price'] * product['series_count']
            item_total = series_price * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'series_price': series_price,
                'item_total': item_total
            })
            total_series += quantity
            subtotal += item_total
            
    conn.close()
    
    discount_percent = 0
    if total_series >= 25:
        discount_percent = 20
    elif total_series >= 10:
        discount_percent = 10
        
    discount_amount = subtotal * (discount_percent / 100)
    total = subtotal - discount_amount
    
    # WhatsApp Mesajı Oluşturma
    wa_text = "Merhaba, B2B portalınızdan toptan sipariş vermek istiyorum:\n\n"
    for item in cart_items:
        p = item['product']
        wa_text += f"- {p['code']} {p['name']} ({item['quantity']} Seri)\n"
    wa_text += f"\nToplam Seri: {total_series}\n"
    wa_text += f"Ara Toplam: {subtotal:.2f} TL\n"
    if discount_percent > 0:
        wa_text += f"Uygulanan İndirim: %{discount_percent} ({discount_amount:.2f} TL)\n"
    wa_text += f"Genel Toplam: {total:.2f} TL\n\nSiparişimi onaylamak isterim."
    
    from urllib.parse import quote
    wa_link = f"https://wa.me/905302772518?text={quote(wa_text)}"
    
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, 
                           discount_percent=discount_percent, discount_amount=discount_amount,
                           total=total, total_series=total_series, wa_link=wa_link)

@app.route('/clear_cart')
def clear_cart():
    session['cart'] = {}
    session.modified = True
    flash('Sepetiniz temizlendi.', 'success')
    return redirect(url_for('cart'))

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
            series_price = product['unit_price'] * product['series_count']
            subtotal += series_price * quantity
            total_series += quantity
            
    conn.close()
    
    discount_percent = 0
    if total_series >= 25:
        discount_percent = 20
    elif total_series >= 10:
        discount_percent = 10
        
    discount_amount = subtotal * (discount_percent / 100)
    total = subtotal - discount_amount
    
    return render_template('checkout.html', subtotal=subtotal, discount_amount=discount_amount, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session or not session.get('cart'):
        return redirect(url_for('cart'))
        
    payment_method = request.form.get('payment_method', 'Kredi Kartı')
    user_id = session['user_id']
    
    conn = get_db_connection()
    subtotal = 0
    total_series = 0
    cart_items = []
    
    for pid, quantity in session['cart'].items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        if product:
            series_price = product['unit_price'] * product['series_count']
            subtotal += series_price * quantity
            total_series += quantity
            cart_items.append((pid, quantity, series_price))
            
    discount_percent = 0
    if total_series >= 25:
        discount_percent = 20
    elif total_series >= 10:
        discount_percent = 10
        
    discount_amount = subtotal * (discount_percent / 100)
    total_price = subtotal - discount_amount
    
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, total_price, discount_amount, payment_method) VALUES (?, ?, ?, ?)', 
                   (user_id, total_price, discount_amount, payment_method))
    order_id = cursor.lastrowid
    
    for pid, qty, sp in cart_items:
        cursor.execute('INSERT INTO order_items (order_id, product_id, quantity, series_price) VALUES (?, ?, ?, ?)',
                       (order_id, pid, qty, sp))
                       
    conn.commit()
    conn.close()
    
    session.pop('cart', None)
    flash(f'Siparişiniz başarıyla alındı. Ödeme Yöntemi: {payment_method}', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        # Database should be initialized via init_db.py, but just in case
        print("Lütfen önce veritabanını oluşturun: python init_db.py")
    app.run(debug=True, port=5000)
