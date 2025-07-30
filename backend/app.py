import sys
import os
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from flask import Flask, render_template
from backend.routes.api import api_bp
from backend.config import Config
from config.logging import setup_logging

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config.from_object(Config)

# Initialize directories
Config.init_dirs()

# Register API blueprint
app.register_blueprint(api_bp, url_prefix="/api")

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    setup_logging()
    print("Running on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)