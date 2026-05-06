import sys
import os
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows PowerShell often defaults to cp1252, which cannot encode some place
# names returned by Google Places. Keep console logging from failing on Unicode.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from flask import Flask, jsonify
from backend.routes.api import api_bp
from backend.app_settings import Config
from backend.database import Database
from config.logging import setup_logging

app = Flask(__name__)
app.config.from_object(Config)

# Initialize directories
Config.init_dirs()

# Run schema creation and migrations once at startup. Database construction is
# intentionally cheap for request/progress hot paths.
Database().initialize()

# Register API blueprint
app.register_blueprint(api_bp, url_prefix="/api")

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "n8n scraping backend is running"})

if __name__ == "__main__":
    with Database() as db:
        setup_logging(log_level=db.get_app_settings()["settings"]["log_level"])
    print("Running on http://localhost:5000")
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
