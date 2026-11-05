import io
import json
import threading
import time
from datetime import date

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from vadaily import exports, pipeline
from vadaily.config import load_config, path_for

cfg = load_config()
SITE = path_for(cfg, "site")
MAX_EXPORT = 20000

app = Flask(__name__, static_folder=None)
_refresh_lock = threading.Lock()


@app.get("/")
def index():
    return send_from_directory(SITE, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(SITE, filename, max_age=0)


def _run_refresh():
    with _refresh_lock:
        return pipeline.run(load_config(), log=print)


@app.post("/api/refresh")
def refresh():
    # Requiring JSON forces a CORS preflight, so other websites can't trigger this.
    if not request.is_json:
        abort(415)
    if not _refresh_lock.acquire(blocking=False):
        return jsonify(error="A refresh is already running."), 409
    try:
        return jsonify(pipeline.run(load_config(), log=app.logger.info))
    except Exception as e:
        app.logger.exception("Refresh failed")
        return jsonify(error=str(e)), 500
    finally:
        _refresh_lock.release()


def _auto_refresh_loop(hours):
    while True:
        time.sleep(hours * 3600)
        try:
            _run_refresh()
        except Exception as e:
            print(f"Auto-refresh failed: {e}")


@app.post("/api/export")
def export():
    body = request.get_json(silent=True) or {}
    fmt = body.get("format")
    keys = body.get("keys")
    if fmt not in exports.FORMATS or not isinstance(keys, list) or len(keys) > MAX_EXPORT:
        abort(400)
    data_file = SITE / "data" / "publications.json"
    if not data_file.exists():
        abort(404)
    by_key = {r["key"]: r for r in json.loads(data_file.read_text(encoding="utf-8"))}
    records = [by_key[k] for k in keys if isinstance(k, str) and k in by_key]
    builder, mimetype, ext = exports.FORMATS[fmt]
    return send_file(io.BytesIO(builder(records)), mimetype=mimetype, as_attachment=True,
                     download_name=f"va-research-{date.today().isoformat()}.{ext}")


if __name__ == "__main__":
    port = int(cfg.get("server", {}).get("port", 5000))
    hours = float(cfg.get("server", {}).get("auto_refresh_hours", 0))
    if hours > 0:
        threading.Thread(target=_auto_refresh_loop, args=(hours,), daemon=True).start()
        print(f"Auto-refresh every {hours:g} hours while this server runs.")
    print(f"Open http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
