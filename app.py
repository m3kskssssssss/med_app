from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for

from services import SourceError, load_comparison

load_dotenv()
app = Flask(__name__)


def get_data():
    doctors, api_count, catalog_count, catalog_pages = load_comparison()
    counts = {status: sum(d["status"] == status for d in doctors) for status in ("matched", "possible", "api_only", "catalog_only")}
    return doctors, counts, api_count, catalog_count, catalog_pages


@app.get("/")
def index():
    try:
        doctors, counts, api_count, catalog_count, catalog_pages = get_data()
        return render_template("index.html", doctors=doctors, counts=counts, api_count=api_count, catalog_count=catalog_count, catalog_pages=catalog_pages, updated_at=datetime.now(), error=None)
    except SourceError as exc:
        return render_template("index.html", doctors=[], counts={}, api_count=0, catalog_count=0, updated_at=None, error=str(exc)), 503


@app.post("/refresh")
def refresh():
    if request.accept_mimetypes.best == "application/json":
        try:
            doctors, counts, api_count, catalog_count, catalog_pages = get_data()
            return jsonify({"ok": True, "doctors": doctors, "counts": counts, "api_count": api_count, "catalog_count": catalog_count, "catalog_pages": catalog_pages})
        except SourceError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
