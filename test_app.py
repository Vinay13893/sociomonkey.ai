"""Minimal Flask test app"""
from flask import Flask, jsonify

test_app = Flask('test')

@test_app.route('/test1')
def test1():
    return jsonify({'message': 'test1 works'}), 200

@test_app.route('/test2')
def test2():
    return jsonify({'message': 'test2 works'}), 200

if __name__ == '__main__':
    print("Starting minimal test Flask app on port 5003...")
    test_app.run(host='127.0.0.1', port=5003, debug=False)
