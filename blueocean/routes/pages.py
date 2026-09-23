from __future__ import annotations

from flask import Blueprint, current_app, render_template, send_from_directory

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/trademap")
def trademap_dashboard():
    """Serve the integrated TradeMap expo/event dashboard as a first-class app page."""
    return send_from_directory(current_app.static_folder, "trademap_dashboard.html")
