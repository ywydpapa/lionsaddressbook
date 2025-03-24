from fastapi import FastAPI, Depends, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
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
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    query = text("SELECT userNo, userName,userRole FROM lionsUser WHERE userId = :username AND userPassword = password(:password)")
    result = await db.execute(query, {"username": username, "password": password})
    user = result.fetchone()
    if user is None:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})
    # 서버 세션에 사용자 ID 저장
    request.session["user_No"] = user[0]
    request.session["user_Name"] = user[1]
    request.session["user_Role"] = user[2]
    return RedirectResponse(url="/success", status_code=303)

# 로그인 성공 페이지
@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html", {"request": request, "user_No": user_No, "user_Name": user_Name, "user_Role": user_Role})

@app.get("/userEdit", response_class=HTMLResponse)
async def user_edit(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login/userEdit.html", {"request": request, "user_No": user_No, "user_Name": user_Name})

@app.get("/userHome", response_class=HTMLResponse)
async def user_home(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html", {"request": request, "user_No": user_No, "user_Name": user_Name})

@app.get("/memberList", response_class=HTMLResponse)
async def memberList(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberList.html", {"request": request, "user_No": user_No, "user_Name": user_Name})

@app.get("/clubList", response_class=HTMLResponse)
async def clubList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    query = text("SELECT * FROM lionsClub where attrib not like '%XXXUP%'")
    result = await db.execute(query)
    club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubList.html", {"request": request, "user_No": user_No, "user_Name": user_Name, "club_list":club_list })

@app.get("/rankList", response_class=HTMLResponse)
async def rankList(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/rankList.html", {"request": request, "user_No": user_No, "user_Name": user_Name})

@app.get("/dictList", response_class=HTMLResponse)
async def dictList(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    club_list = await get_clublist(async_session)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/dictList.html", {"request": request, "user_No": user_No, "user_Name": user_Name, "club_list":club_list })

@app.get("/boardManager", response_class=HTMLResponse)
async def boardManager(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/boardMain.html", {"request": request, "user_No": user_No, "user_Name": user_Name})

# 로그아웃 처리
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()  # 세션 삭제
    return RedirectResponse(url="/")

@app.post("/mlogin")
async def mlogin(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    query = text("SELECT memberNo FROM lionsMember WHERE memberName = :username AND mbPassword = password(:password)")
    result = await db.execute(query, {"username": username, "password": password})
    user = result.fetchone()
    if user is None:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})
    # 서버 세션에 사용자 ID 저장
    request.session["user_No"] = user[0]
    return RedirectResponse(url="/success", status_code=303)

@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "/error/errorInfo.html",  # 템플릿 파일
            {"request": request, "error_message": "페이지를 찾을 수 없습니다."},  # 템플릿에 전달할 데이터
            status_code=404,
        )
    if exc.status_code == 500:
        return templates.TemplateResponse(
            "/error/errorInfo.html",  # 템플릿 파일
            {"request": request, "error_message": "시스템 내부 에러 발생."},  # 템플릿에 전달할 데이터
            status_code=500,
        )
    return HTMLResponse(
        content=f"<h1>{exc.status_code} - {exc.detail}</h1>",
        status_code=exc.status_code,
    )