from fastapi import FastAPI, Depends, Request, Form, Response, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
import dotenv
import os
import base64

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


async def get_clublist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClub where attrib not like :attpatt")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return club_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBLIST)")


def get_default_image_base64(mime_type: str = "image/png") -> str:
    default_image_path = "static/img/defaultphoto.png"
    try:
        with open(default_image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_image}"
    except FileNotFoundError:
        raise Exception("Default image file not found.")


async def get_photo(memberNo:int, db:AsyncSession, mime_type: str = "image/jpeg") -> str:
    try:
        query = text("SELECT mphoto FROM memberPhoto WHERE memberNo = :memberNo")
        result = await db.execute(query, {"memberNo": memberNo})
        photo = result.fetchone()
        if photo is None:
            return get_default_image_base64(mime_type)
        base64_image = base64.b64encode(photo[0]).decode("utf-8")
        return base64_image
    except:
        raise HTTPException(status_code=500, detail="Database query failed(Photo)")


async def get_regionclublist(region: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClub where attrib not like :attpatt and regionNo = :regno")
        result = await db.execute(query, {"attpatt": "%XXX%", "regno": region})
        club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return club_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")


async def get_regionmemberlist(region: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lcc.clubName  FROM lionsMember lm left join lionsClub lcc on lm.clubNo = lcc.clubNo where lm.clubNo in (select lc.clubno from lionsClub lc where lc.regionNo = :regno)")
        result = await db.execute(query, {"regno": region})
        rmember_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return rmember_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")


async def get_memberdetail(memberon: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsMember where memberNo = :memberno")
        result = await db.execute(query, {"memberno": memberon})
        memberdtl = result.fetchone()  # 클럽 데이터를 모두 가져오기
        return memberdtl
    except:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")


async def get_clubmemberlist(clubno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsMember where clubNo = :club_no")
        result = await db.execute(query, {"club_no": clubno})
        member_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        member = [
            {
                "memberNo": row.memberNo,
                "memberName": row.memberName,
                "memberPhone": row.memberPhone,
                "memberEmail": row.memberEmail,
                "memberMF": row.memberMF
            }
            for row in member_list
        ]
        return {"members": member}
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBMemberLIST)")


async def get_dictlist(db: AsyncSession):
    try:
        query = text(
            "SELECT lr.*, GROUP_CONCAT(lc.clubName SEPARATOR ', ') AS clubNames FROM lionsaddr.lionsRegion lr "
            "LEFT JOIN lionsaddr.lionsClub lc ON lr.regionNo = lc.regionNo where lr.attrib not like :attpatt GROUP BY lr.regionNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        dict_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return dict_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(DICT)")


async def get_ranklist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where attrib not like :attpatt order by orderNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        rank_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return rank_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")


@app.get("/favicon.ico")
async def favicon():
    return {"detail": "Favicon is served at /static/favicon.ico"}

@app.post("/upload/")
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")

        # 파일 읽기
        contents = await file.read()

        # 데이터베이스에 이미지 저장
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("INSERT INTO images (image) VALUES (?)", (contents,))
        conn.commit()
        image_id = cursor.lastrowid

        return templates.TemplateResponse("upload_form.html",
                                          {"request": request, "filename": file.filename, "id": image_id})

    except Exception as e:
        return templates.TemplateResponse("upload_form.html", {"request": request, "error": str(e)})


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
    query = text(
        "SELECT userNo, userName,userRole FROM lionsUser WHERE userId = :username AND userPassword = password(:password)")
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
    return templates.TemplateResponse("member/mainClub.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "user_Role": user_Role})


@app.get("/userEdit", response_class=HTMLResponse)
async def user_edit(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login/userEdit.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name})


@app.get("/userHome", response_class=HTMLResponse)
async def user_home(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name})


@app.get("/rmemberList/{regno}", response_class=HTMLResponse)
async def memberList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    rmember = await get_regionmemberlist(regno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/regionmemberList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "rmember": rmember})


@app.get("/memberdetail/{memberno}", response_class=HTMLResponse)
async def memberList(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    memberdtl = await get_memberdetail(memberno, db)
    print(memberdtl)
    myphoto = await get_photo(memberno, db)
    print(myphoto)
    if not user_No:
        return RedirectResponse(url="/")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "memberdtl": memberdtl, "myphoto": myphoto})


@app.post("/uploadphoto/{memberno}", response_class=HTMLResponse)
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        # 파일 읽기
        contents = await file.read()
        # 데이터베이스에 이미지 저장
        return templates.TemplateResponse("member/memberDetail.html",
                                          {"request": request, "filename": file.filename, "id": image_id})
    except Exception as e:
        return templates.TemplateResponse("member/memberDetail.html", {"request": request, "error": str(e)})


@app.get("/clubmemberList/{clubno}/{clubname}", response_class=HTMLResponse)
async def memberList(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    memberList = await get_clubmemberlist(clubno, db)
    print(memberList)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubName": clubname, "memberList": memberList})


@app.get("/clubList", response_class=HTMLResponse)
async def clubList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    query = text("SELECT * FROM lionsClub where attrib not like '%XXXUP%'")
    result = await db.execute(query)
    club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "club_list": club_list})


@app.get("/regionclubList/{regno}", response_class=HTMLResponse)
async def regionclubList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    club_list = await get_regionclublist(regno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/regionclubList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "club_list": club_list})


@app.get("/rankList", response_class=HTMLResponse)
async def rankList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    rank_list = await get_ranklist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/rankList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "rank_list": rank_list})


@app.get("/dictList", response_class=HTMLResponse)
async def dictList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    club_list = await get_clublist(db)
    dict_list = await get_dictlist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/regionList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "club_list": club_list, "dict_list": dict_list})


@app.get("/boardManager", response_class=HTMLResponse)
async def boardManager(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/boardMain.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name})


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
