import sys
import os
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify
from backend.routes.api import api_bp
from backend.app_settings import Config
from config.logging import setup_logging

app = Flask(__name__)
app.config.from_object(Config)

# Initialize directories
Config.init_dirs()

# Register API blueprint
app.register_blueprint(api_bp, url_prefix="/api")

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "n8n scraping backend is running"})

if __name__ == "__main__":
    setup_logging()
    print("Running on http://localhost:5000")
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)