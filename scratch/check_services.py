import sys
sys.path.insert(0, '.')
from app import create_app
app = create_app()
with app.app_context():
    from routes.it_services import _public_services
    services = _public_services()
    for s in services:
        print(s['title'], '->', s['icon'])
