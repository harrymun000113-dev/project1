from __future__ import annotations

from flask import Blueprint, current_app, render_template

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/trademap")
def trademap():
    return current_app.send_static_file("trademap/index.html")
