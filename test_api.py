"""Quick API integration test for PingPlace."""
import json
from app import create_app

app = create_app()

with app.test_client() as c:
    # Test 1: GET /
    resp = c.get('/')
    print(f'Test 1 - GET /: {resp.status_code}')

    # Test 2: POST /api/device (no cookie)
    resp = c.post('/api/device')
    print(f'Test 2 - POST /api/device (new): {resp.status_code}')
    data = resp.get_json()
    device_id = data.get('device_id', 'MISSING')
    is_new = data.get('is_new', 'MISSING')
    print(f'  device_id: {device_id}')
    print(f'  is_new: {is_new}')

    cookies = resp.headers.getlist('Set-Cookie')
    has_cookie = any('pingplace_device' in c2 for c2 in cookies)
    print(f'  cookie set: {has_cookie}')

    # Test 3: GET /api/destinations (should get 401 without cookie)
    resp2 = c.get('/api/destinations')
    print(f'Test 3 - GET /api/destinations (no cookie): {resp2.status_code} (expect 401)')

    # Get real cookie token from DB
    from models.device import Device
    with app.app_context():
        device = Device.query.first()
        if device:
            real_token = device.cookie_token
            print(f'  DB cookie_token prefix: {str(real_token)[:8]}...')
        else:
            print('  No device in DB!')
            real_token = None

    if real_token:
        # Test 4: List destinations with real cookie
        resp4 = c.get('/api/destinations', headers={'Cookie': f'pingplace_device={real_token}'})
        print(f'Test 4 - GET /api/destinations (with cookie): {resp4.status_code}')
        print(f'  destinations: {resp4.get_json()}')

        # Test 5: Create a destination
        dest_data = {
            'name': 'Test Home',
            'address': '123 Main St, New York, NY 10001',
            'place_id': 'ChIJtest1234567890',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'alert_threshold_minutes': 10
        }
        resp5 = c.post(
            '/api/destinations',
            json=dest_data,
            headers={'Cookie': f'pingplace_device={real_token}'}
        )
        print(f'Test 5 - POST /api/destinations: {resp5.status_code}')
        if resp5.status_code == 201:
            dest = resp5.get_json()
            dest_id = dest['id']
            print(f'  dest id: {dest_id[:8]}...')

            # Test 6: GET /api/alert/active
            resp6 = c.get('/api/alert/active', headers={'Cookie': f'pingplace_device={real_token}'})
            print(f'Test 6 - GET /api/alert/active: {resp6.status_code}')
            print(f'  data: {resp6.get_json()}')

            # Test 7: Start alert
            resp7 = c.post(
                '/api/alert/start',
                json={'destination_id': dest_id},
                headers={'Cookie': f'pingplace_device={real_token}'}
            )
            print(f'Test 7 - POST /api/alert/start: {resp7.status_code}')
            if resp7.status_code == 201:
                session_data = resp7.get_json()
                session_id = session_data['alert_session_id']
                print(f'  session_id: {session_id[:8]}...')

                # Test 8: POST /api/eta
                resp8 = c.post(
                    '/api/eta',
                    json={
                        'latitude': 40.7128,
                        'longitude': -74.0060,
                        'destination_id': dest_id
                    },
                    headers={'Cookie': f'pingplace_device={real_token}'}
                )
                print(f'Test 8 - POST /api/eta: {resp8.status_code}')
                eta_result = resp8.get_json()
                print(f'  status: {eta_result.get("status")}')
                print(f'  eta_minutes: {eta_result.get("eta_minutes")}')
                print(f'  eta_text: {eta_result.get("eta_text")}')
                if 'error' in eta_result:
                    print(f'  error: {eta_result.get("error")}')

                # Test 9: Stop alert
                resp9 = c.post(
                    '/api/alert/stop',
                    json={'alert_session_id': session_id, 'reason': 'user_stopped'},
                    headers={'Cookie': f'pingplace_device={real_token}'}
                )
                print(f'Test 9 - POST /api/alert/stop: {resp9.status_code}')
                print(f'  data: {resp9.get_json()}')

                # Test 10: PUT /api/destinations/<id>
                resp10 = c.put(
                    f'/api/destinations/{dest_id}',
                    json={'alert_threshold_minutes': 15},
                    headers={'Cookie': f'pingplace_device={real_token}'}
                )
                print(f'Test 10 - PUT /api/destinations/<id>: {resp10.status_code}')
                if resp10.status_code == 200:
                    updated = resp10.get_json()
                    print(f'  updated threshold: {updated.get("alert_threshold_minutes")}')

                # Test 11: DELETE /api/destinations/<id>
                resp11 = c.delete(
                    f'/api/destinations/{dest_id}',
                    headers={'Cookie': f'pingplace_device={real_token}'}
                )
                print(f'Test 11 - DELETE /api/destinations/<id>: {resp11.status_code}')
            else:
                print(f'  error: {resp7.get_json()}')
        else:
            print(f'  error: {resp5.get_json()}')
