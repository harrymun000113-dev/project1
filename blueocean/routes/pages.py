from __future__ import annotations

<<<<<<< HEAD
from flask import Blueprint, current_app, render_template, send_from_directory
=======
from flask import Blueprint, current_app, render_template
>>>>>>> 681d5d6a37cd7fe50fef594f99a939401091a899

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/trademap")
<<<<<<< HEAD
def trademap_dashboard():
    """Serve the integrated TradeMap expo/event dashboard as a first-class app page."""
    return send_from_directory(current_app.static_folder, "trademap_dashboard.html")
=======
def trademap():
    return current_app.send_static_file("trademap/index.html")
>>>>>>> 681d5d6a37cd7fe50fef594f99a939401091a899
