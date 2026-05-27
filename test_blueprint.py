"""Blueprint test app"""
from flask import Flask, Blueprint, jsonify

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/test1')
def test1():
    return jsonify({'message': 'blueprint test1 works'}), 200

@bp.route('/test2')
def test2():
    return jsonify({'message': 'blueprint test2 works'}), 200

test_app2 = Flask('test2')
test_app2.register_blueprint(bp)

if __name__ == '__main__':
    print("Starting blueprint test Flask app on port 5004...")
    test_app2.run(host='127.0.0.1', port=5004, debug=False)
