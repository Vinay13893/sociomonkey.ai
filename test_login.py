import json
import os
import urllib.request


def main():
    email = (os.getenv('LMS_TEST_EMAIL') or '').strip()
    password = os.getenv('LMS_TEST_PASSWORD') or ''
    if not email or not password:
        raise SystemExit(
            'Set LMS_TEST_EMAIL and LMS_TEST_PASSWORD before running this '
            'manual login check.'
        )
    url = (
        os.getenv('LMS_TEST_LOGIN_URL')
        or 'http://127.0.0.1:5000/api/auth/login'
    )
    data = json.dumps({'email': email, 'password': password}).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        print(response.status)


if __name__ == '__main__':
    main()
