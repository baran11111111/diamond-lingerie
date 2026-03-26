import sys, traceback
from app import app
app.testing = True
app.config['PROPAGATE_EXCEPTIONS'] = True
client = app.test_client()

try:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['is_admin'] = True
        sess['cart'] = {'5': 30} # over 25 items triggers discount!

    routes = ['/checkout']
    for r in routes:
        print(f"GET {r}")
        res = client.get(r)
        if res.status_code == 500:
            print("FAILED:", r)
    print("ALL OK")
except Exception as e:
    traceback.print_exc()
