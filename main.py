from fastapi import FastAPI, Depends, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from itsdangerous import URLSafeSerializer
import dotenv
import os

dotenv.load_dotenv()
# 데이터베이스 설정
DATABASE_URL = os.getenv("dburl")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# FastAPI 앱 초기화
app = FastAPI()

# 세션 미들웨어 추가 (서버에서 세션 관리)
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

templates = Jinja2Templates(directory="templates")

# 데이터베이스 세션 생성
async def get_db():
    async with async_session() as session:
        yield session

# 로그인 폼 페이지
@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    if request.session.get("user_No"):
        return RedirectResponse(url="/success", status_code=303)

    return templates.TemplateResponse("login/login.html", {"request": request})

# 로그인 요청 처리
@app.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    query = text("SELECT userNo FROM lionsUser WHERE userName = :username AND userPassword = password(:password)")
    result = await db.execute(query, {"username": username, "password": password})
    user = result.fetchone()

    if user is None:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})

    # 서버 세션에 사용자 ID 저장
    request.session["user_No"] = user[0]
    return RedirectResponse(url="/success", status_code=303)

# 로그인 성공 페이지
@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    user_No = request.session.get("user_No")

    if not user_No:
        return RedirectResponse(url="/")

    return templates.TemplateResponse("login/success.html", {"request": request, "user_id": user_No})

# 로그아웃 처리
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()  # 세션 삭제
    return RedirectResponse(url="/")