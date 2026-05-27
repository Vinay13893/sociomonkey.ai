from app import create_app
import os

# Force Flask auto-reload
config_name = os.getenv('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5002))
    app.run(host=host, port=port, debug=False)
