import sys, traceback
from app import app
app.testing = True
app.config['PROPAGATE_EXCEPTIONS'] = True
client = app.test_client()

try:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['is_admin'] = True
        sess['cart'] = {'5': 1}

    print("GET /cart")
    client.get('/cart')
    print("GET /checkout")
    client.get('/checkout')
    print("POST /place_order")
    client.post('/place_order', data={'payment_method': 'Havale'})
    print("ALL OK")
except Exception as e:
    traceback.print_exc()
