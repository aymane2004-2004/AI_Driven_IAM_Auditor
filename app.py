from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

JOBS: dict[str, dict] = {}


def format_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_input_file(file_name: str) -> str:
    if not file_name:
        return "iam_inventory.json"
    if file_name.startswith("data/"):
        return file_name
    if (BASE_DIR / "data" / file_name).exists():
        return str(Path("data") / file_name)
    return file_name


def build_artifacts() -> list[dict]:
    files = []
    for p in sorted(OUTPUT_DIR.glob("*"), key=lambda item: item.name):
        if p.is_file():
            files.append({
                "name": p.name,
                "path": str(p.relative_to(BASE_DIR)),
                "url": url_for("download_file", filename=p.name),
            })
    return files


def update_job(job_id: str, **kwargs) -> None:
    job = JOBS.setdefault(job_id, {})
    for key, value in kwargs.items():
        job[key] = value
    job.setdefault("logs", [])


def run_audit_job(job_id: str, args: list[str]) -> None:
    log_path = LOG_DIR / f"{job_id}.log"
    update_job(job_id, status="running", started_at=format_now(), command=" ".join(args))

    try:
        with log_path.open("w", encoding="utf-8") as fp:
            proc = subprocess.Popen(
                [sys.executable, "src/audit.py", *args],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            logs: list[str] = []
            for line in proc.stdout or []:
                cleaned = line.rstrip()
                if cleaned:
                    logs.append(cleaned)
                    fp.write(cleaned + "\n")
                    fp.flush()
                    if len(logs) > 200:
                        logs = logs[-200:]
                    update_job(job_id, logs=logs)

            exit_code = proc.wait()
            update_job(job_id, exit_code=exit_code)

            if exit_code == 0:
                update_job(job_id, status="completed", finished_at=format_now(), artifacts=build_artifacts())
            else:
                update_job(job_id, status="failed", finished_at=format_now(), artifacts=build_artifacts())

    except Exception as exc:  # pragma: no cover - UI safety branch
        update_job(job_id, status="failed", finished_at=format_now(), error=str(exc))


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/run")
def run_audit():
    input_file = resolve_input_file(request.form.get("input_file", "iam_inventory.json"))
    no_llm = bool(request.form.get("no_llm"))
    deep = bool(request.form.get("deep_mode"))

    args = []
    if no_llm:
        args.append("--no-llm")
    if deep:
        args.append("--deep")
    if input_file and input_file != "iam_inventory.json":
        args.extend(["--input", Path(input_file).name])

    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "logs": [],
        "artifacts": [],
        "error": None,
        "command": "python src/audit.py " + " ".join(args),
    }

    thread = threading.Thread(target=run_audit_job, args=(job_id, args), daemon=True)
    thread.start()
    return redirect(url_for("job_detail", job_id=job_id))


@app.get("/jobs/<job_id>")
def job_detail(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return "Job not found", 404
    return render_template("job.html", job=job)


@app.get("/api/jobs/<job_id>")
def job_api(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job["artifacts"] = build_artifacts()
    return jsonify(job)


@app.get("/download/<path:filename>")
def download_file(filename: str):
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=False)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
