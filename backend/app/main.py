"""Alzheimer Care Companion - API server.

Run locally:   uvicorn app.main:app --reload --port 8000
One process serves both the API (/api/...) and the built web app (/), so a
single free Render service hosts the whole product.
"""
import html
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, SessionLocal, engine
from .routers import ask, auth, care, memories
from .services.seed import seed_demo

static_dir = os.path.abspath(settings.STATIC_DIR)
web_app_found = os.path.isfile(os.path.join(static_dir, "index.html")) and os.path.isdir(os.path.join(static_dir, "assets"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.DEMO_SEED:
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()
    if web_app_found:
        print(f"INFO:     Web app: serving {static_dir}")
        if os.getenv("OPEN_BROWSER") == "1":  # optional: opens the browser on start
            import threading
            import webbrowser
            print("INFO:     Opening http://localhost:8000 in your browser")
            threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    else:
        print(f"WARNING:  Web app not found at {static_dir}")
        print("WARNING:  Only the API is available. Build it with 'npm run build' in the frontend folder,")
        print("WARNING:  or set STATIC_DIR to the folder that contains index.html.")
    yield


app = FastAPI(title="Alzheimer Care Companion API", version="0.6.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, memories.router, ask.router, care.router):
    app.include_router(r)


@app.exception_handler(Exception)
async def unhandled(_request, exc):
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Try again."})


def _inside_static(target: str) -> bool:
    """True only for files under static_dir. Blocks ../ escapes and other drives on Windows."""
    try:
        return os.path.commonpath([static_dir, target]) == static_dir
    except ValueError:  # different drive letters
        return False


if web_app_found:
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        target = os.path.abspath(os.path.join(static_dir, path))
        if path and _inside_static(target) and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    _MISSING_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Web app not built</title></head>
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:48px auto;padding:0 20px;line-height:1.55;color:#1e2a5a">
<h1 style="font-size:1.6rem">The API is running, but the web app was not found</h1>
<p>The server looked for the built web app here:</p>
<pre style="background:#f3f5fa;padding:12px;border-radius:8px;white-space:pre-wrap">{path}</pre>
<p><b>Fix one of these ways, then restart the server:</b></p>
<ol>
<li>Make sure that folder exists and contains <code>index.html</code> and an <code>assets</code> folder
(for example, extract the project zip again into the same place and choose <i>Replace</i>).</li>
<li>Or build it: in the <code>frontend</code> folder run <code>npm install</code> then <code>npm run build</code>.</li>
<li>Or, while developing, run <code>npm run dev</code> in the <code>frontend</code> folder and open
<a href="http://localhost:5173">http://localhost:5173</a>.</li>
</ol>
<p>The API itself is fine: <a href="/api/health">/api/health</a> and <a href="/docs">/docs</a> work.</p>
</body></html>"""

    @app.get("/{path:path}", include_in_schema=False)
    def web_app_missing(path: str):
        if path.startswith("api/") or path in ("docs", "redoc", "openapi.json"):
            raise HTTPException(404, "Not found.")
        return HTMLResponse(_MISSING_PAGE.format(path=html.escape(static_dir)), status_code=503)
