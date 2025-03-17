import os

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import jinja2
import base64
import mariadb
import dotenv

dotenv.load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATABASE_CONFIG = {
    "host": os.getenv("host"),
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "database": os.getenv("database"),
}

def get_dbconnection():
    try:
        conn = mariadb.connect(**DATABASE_CONFIG)
        return conn
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB: {e}")
        raise

def format_currency(value):
    if isinstance(value, (int, float)):
        return "₩{:,.0f}".format(value)
    return value

@app.get("/")
async def root():
    get_dbconnection()
    return {"message": "Hello World"}


@app.get("/login", response_class=HTMLResponse)
async def get_upload_form(request: Request):
    return templates.TemplateResponse("./login/login.html", {"request": request})