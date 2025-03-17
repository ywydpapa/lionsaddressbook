from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.templating import Jinja2Templates
import jinja2
import base64
import mariadb


app = FastAPI()
templates = Jinja2Templates(directory="./templates")

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
