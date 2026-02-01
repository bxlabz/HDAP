from flask import Flask
import os
import tempfile

app = Flask(__name__,
            template_folder='templates',
            static_folder='../static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Data storage directory
app.config['DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'textgen_data')
os.makedirs(app.config['DATA_DIR'], exist_ok=True)

from app.routes import bp
app.register_blueprint(bp)

@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'textgen'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
