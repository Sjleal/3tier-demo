import os, logging
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import PlainTextResponse

from db import get_conn, get_db_creds
from aws_meta import get_instance_info, cpu_percent
from load_test import start_load_test

log = logging.getLogger("demoapp")
app = FastAPI(title="3-Tier Demo App")
templates = Jinja2Templates(directory="templates")

TABLE = os.environ.get("DB_TABLE", "contacts")


def ensure_schema():
  creds = get_db_creds()
  log.info(f"Ensuring schema on host={creds.host} db={creds.dbname} table={TABLE}")
  sql = f"""
  CREATE TABLE IF NOT EXISTS {TABLE} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(120) NOT NULL
  );
  """
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)

@app.post("/init-db")
def init_db():
  ensure_schema()
  return {"ok": True}

@app.on_event("startup")
def _startup():
  if os.getenv("DB_INIT_ON_STARTUP", "false").lower() == "true":
    try:
      ensure_schema()
    except Exception as e:
      log.exception("DB init failed (continuing anyway): %s", e)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
  info = get_instance_info()
  cpu = cpu_percent()
  return templates.TemplateResponse(
    "home.html",
    {
      "request": request,
      "instance_id": info["instance_id"],
      "az": info["az"],
      "cpu": cpu,
    },
  )


@app.get("/health", response_class=PlainTextResponse)
def health():
  return "ok"


@app.post("/load-test")
def load_test(seconds: int = Form(30), threads: int = Form(2)):
  start_load_test(seconds=seconds, threads=threads)
  return RedirectResponse(url="/", status_code=303)


@app.get("/rds", response_class=HTMLResponse)
def rds(request: Request):
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT id, name, phone, email FROM {TABLE} ORDER BY id ASC;")
      rows = cur.fetchall()
  return templates.TemplateResponse("rds.html", {"request": request, "rows": rows})


@app.post("/seed")
def seed():
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"INSERT INTO {TABLE} (name, phone, email) VALUES (%s,%s,%s)", ("Alice", "111-111", "alice@example.com"))
      cur.execute(f"INSERT INTO {TABLE} (name, phone, email) VALUES (%s,%s,%s)", ("Bob", "222-222", "bob@example.com"))
  return RedirectResponse(url="/rds", status_code=303)


@app.get("/add", response_class=HTMLResponse)
def add_form(request: Request):
  return templates.TemplateResponse("add.html", {"request": request})


@app.post("/add")
def add(name: str = Form(...), phone: str = Form(...), email: str = Form(...)):
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"INSERT INTO {TABLE} (name, phone, email) VALUES (%s,%s,%s)", (name, phone, email))
  return RedirectResponse(url="/rds", status_code=303)


@app.get("/edit/{row_id}", response_class=HTMLResponse)
def edit_form(request: Request, row_id: int):
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT id, name, phone, email FROM {TABLE} WHERE id=%s", (row_id,))
      row = cur.fetchone()
  return templates.TemplateResponse("edit.html", {"request": request, "row": row})


@app.post("/edit/{row_id}")
def edit(row_id: int, name: str = Form(...), phone: str = Form(...), email: str = Form(...)):
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"UPDATE {TABLE} SET name=%s, phone=%s, email=%s WHERE id=%s", (name, phone, email, row_id))
  return RedirectResponse(url="/rds", status_code=303)


@app.post("/delete/{row_id}")
def delete(row_id: int):
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute(f"DELETE FROM {TABLE} WHERE id=%s", (row_id,))
  return RedirectResponse(url="/rds", status_code=303)






