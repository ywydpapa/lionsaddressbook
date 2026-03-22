import os
import datetime
from datetime import timedelta
from pathlib import Path
import asyncio
from io import BytesIO
import dotenv
from fastapi import FastAPI, Depends, Request, Form, Response, HTTPException, File, UploadFile, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pydantic import BaseModel
import jwt
import firebase_admin
from firebase_admin import credentials
from funchub import *
from PIL import Image
import io
import os


dotenv.load_dotenv()
DATABASE_URL = os.getenv("dburl")
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=1800)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "supersecretkey"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/thumbnails", StaticFiles(directory="static/img/members/"), name="thumbnails")
MEMBERPHOTO_DIR = "./static/img/members"
BASE_DIR = Path(__file__).resolve().parent
cred = credentials.Certificate(
    str(BASE_DIR / "common" / "r15addr-firebase-adminsdk-fbsvc-87610d6413.json")
)

firebase_admin.initialize_app(cred)
security = HTTPBearer()


# 토큰 검증 함수 (API 호출 시마다 실행됨)
async def get_current_mobile_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        memberno: str = payload.get("sub")
        if memberno is None:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
        return memberno
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다. 다시 로그인해주세요.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="잘못된 토큰입니다.")


# 데이터베이스 세션 생성
async def get_db():
    async with async_session() as session:
        yield session


@app.get("/favicon.ico")
async def favicon():
    return {"detail": "Favicon is served at /static/favicon.ico"}


@app.post("/uploaddoc/{clubno}")
async def upload_doc(request: Request, clubno: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        contents = await file.read()
        query = text("INSERT INTO lionsDoc (clubNo,cDocument) VALUES (:memno, :docs)")
        result = await db.execute(query, {"memno": clubno, "docs": contents})
        await db.commit()
        return RedirectResponse(f"/doclist/{clubno}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/doclist/{clubno}", status_code=303)


@app.post("/upload/{memberno}")
async def upload_image(request: Request, memberno: int, file: UploadFile = File(...),
                       db: AsyncSession = Depends(get_db)):
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        contents = await file.read()
        contents = await resize_image_if_needed(contents, max_bytes=102400)
        os.makedirs(MEMBERPHOTO_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(contents))
        thumbnail_path = os.path.join(MEMBERPHOTO_DIR, f"mphoto_{memberno}.png")
        image.save(thumbnail_path, format="PNG")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.post("/uploadnamecard/{memberno}")
async def upload_ncimage(request: Request, memberno: int, file: UploadFile = File(...),
                         db: AsyncSession = Depends(get_db)):
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        contents = await file.read()
        contents = await resize_image_if_needed(contents, max_bytes=102400)
        os.makedirs(MEMBERPHOTO_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(contents))
        thumbnail_path = os.path.join(MEMBERPHOTO_DIR, f"ncard_{memberno}.png")
        image.save(thumbnail_path, format="PNG")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.post("/uploadspphoto/{memberno}")
async def upload_spimage(request: Request, memberno: int, file: UploadFile = File(...),
                         db: AsyncSession = Depends(get_db)):
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        contents = await file.read()
        contents = await resize_image_if_needed(contents, max_bytes=102400)
        os.makedirs(MEMBERPHOTO_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(contents))
        thumbnail_path = os.path.join(MEMBERPHOTO_DIR, f"sphoto_{memberno}.png")
        image.save(thumbnail_path, format="PNG")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    if request.session.get("user_No"):
        return RedirectResponse(url="/success", status_code=303)
    return templates.TemplateResponse("login/login.html", {"request": request})


@app.post("/login")
async def login(request: Request, response: Response, username: str = Form(...), password: str = Form(...),
                db: AsyncSession = Depends(get_db)):
    query = text(
        "SELECT userNo, userName, userRole, defaultRegion, defaultClubno, userPassword FROM lionsUser WHERE userId = :username")
    result = await db.execute(query, {"username": username})
    user = result.fetchone()

    if not user:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})

    user_no = user[0]
    stored_password = user[5] or ""
    authenticated = False

    if verify_password(password, stored_password):
        authenticated = True
    elif isinstance(stored_password, str) and stored_password.strip() == password:
        new_hashed_password = get_password_hash(password)
        update_sql = text("UPDATE lionsUser SET userPassword = :passwd WHERE userNo = :userno")
        await db.execute(update_sql, {"passwd": new_hashed_password, "userno": user_no})
        await db.commit()
        authenticated = True

    if not authenticated:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})

    request.session["user_No"] = user[0]
    request.session["user_Name"] = user[1]
    request.session["user_Role"] = user[2]
    request.session["user_Region"] = user[3]
    request.session["user_Clubno"] = user[4]

    return RedirectResponse(url="/success", status_code=303)


@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/userEdit", response_class=HTMLResponse)
async def user_edit(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    userdtl = await get_userdtl(user_No, db)
    clublist = await get_clublist(db)
    return templates.TemplateResponse("login/userEdit.html", {
        "request": request, "user_No": user_No, "user_Role": request.session.get("user_Role"),
        "user_Name": request.session.get("user_Name"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "userdtl": userdtl, "clublist": clublist
    })


@app.post("/changeuserpass")
async def change_password(data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    hashed_password = get_password_hash(data["passwd"])
    sql = text("UPDATE lionsUser SET userPassword = :passwd WHERE userNo = :userno")
    await db.execute(sql, {"passwd": hashed_password, "userno": data["uno"]})
    await db.commit()
    return {"result": "success"}


@app.get("/userHome", response_class=HTMLResponse)
async def user_home(request: Request):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/rmemberList/{regno}", response_class=HTMLResponse)
async def rmemberList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    rmember = await get_regionmemberlist(regno, db)
    return templates.TemplateResponse("member/regionmemberList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "rmember": rmember,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/getcirclemembers/{circleno}", response_class=JSONResponse)
async def getcirclemembers(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    rows = await get_circlememberlist(circleno, db)
    members = [row_to_dict(row) for row in rows]
    return JSONResponse({"members": members})


@app.get("/circlememberList/{circleno}", response_class=HTMLResponse)
async def ccmemberList(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    allmembers = await get_memberlist(db)
    cmember = await get_circlememberlist(circleno, db)
    circledtl = await get_circledtl(circleno, db)
    return templates.TemplateResponse("member/circlememberList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "circledtl": circledtl, "cmembers": cmember,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno"),
        "allmembers": allmembers
    })


@app.get("/editcirclemember/{circleno}/{memberno}", response_class=HTMLResponse)
async def editcirclemember(request: Request, circleno: int, memberno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    ranks = await get_ranklistcircle(db)
    cmemberdtl = await get_circlememberdtl(circleno, memberno, db)
    return templates.TemplateResponse("member/circlememberdtl.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "circlerank": ranks, "cmember": cmemberdtl,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/memberList", response_class=HTMLResponse)
async def memberList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    members = await get_memberlist(db)
    return templates.TemplateResponse("admin/memberList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "members": members,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.api_route("/addmember", response_class=HTMLResponse, methods=["GET", "POST"])
async def addmember(request: Request, db: AsyncSession = Depends(get_db)):
    memberName = "신규추가 회원"
    insert_q = text("INSERT INTO lionsMember (memberName) VALUES (:membername)")
    await db.execute(insert_q, {"membername": memberName})
    id_q = text("SELECT LAST_INSERT_ID()")
    result = await db.execute(id_q)
    new_memberno = result.scalar_one()
    await db.commit()
    return RedirectResponse(url=f"/memberdetail/{new_memberno}", status_code=303)


@app.api_route("/addcircle", response_class=HTMLResponse, methods=["GET", "POST"])
async def addcircle(request: Request, db: AsyncSession = Depends(get_db)):
    circleName = "신규추가 써클"
    query = text(f"INSERT into lionsCircle (circleName) values (:circlename)")
    await db.execute(query, {"circlename": circleName})
    await db.commit()
    return RedirectResponse("/circleList", status_code=303)


@app.get("/memberdetail/{memberno}", response_class=HTMLResponse)
async def memberDetail(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    memberdtl = await get_memberdetail(memberno, db)
    myphoto = await get_photo(memberno, db)
    ncphoto = await get_namecard(memberno, db)
    spphoto = await get_spphoto(memberno, db)
    clublist = await get_clublist(db)
    ranklist = await get_ranklist(db)
    return templates.TemplateResponse("member/memberDetail.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "memberdtl": memberdtl, "myphoto": myphoto,
        "clublist": clublist, "ranklist": ranklist, "ncphoto": ncphoto, "spphoto": spphoto,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.post("/update_memberdtl/{memberno}", response_class=HTMLResponse)
async def update_memberdtl(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "memberName": form_data.get("membername"), "memberMF": form_data.get("gender"),
        "memberBirth": form_data.get("birthdate"),
        "memberSns": form_data.get("memberSns"), "memberSeccode": form_data.get("contact").replace('-', ''),
        "memberAddress": form_data.get("home_address"),
        "memberPhone": form_data.get("contact"), "memberEmail": form_data.get("email"),
        "memberJoindate": form_data.get("joindate"),
        "clubNo": form_data.get("clublst"), "sponserNo": form_data.get("sponserNo"), "addMemo": form_data.get("memo"),
        "rankNo": form_data.get("ranklst"), "officeAddress": form_data.get("office_address"),
        "spouseName": form_data.get("spname"),
        "spousePhone": form_data.get("spphone"), "spouseBirth": form_data.get("spbirth"),
        "clubRank": form_data.get("clubrank"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE lionsMember SET {set_clause} WHERE memberNo = :memberNo")
    update_fields["memberNo"] = memberno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.get("/clubmemberList/{clubno}/{clubname}", response_class=HTMLResponse)
async def clubmemberList(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    cmembers = await get_clubmemberlist(clubno, db)
    return templates.TemplateResponse("member/memberList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clubName": clubname, "cmembers": cmembers,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/clubmemberCards/{clubno}/{clubname}", response_class=HTMLResponse)
async def clubmemberCards(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    memberList = await get_clubmembercard(clubno, db)
    return templates.TemplateResponse("member/memberCards.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clubName": clubname, "memberList": memberList,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/clubList", response_class=HTMLResponse)
async def clubList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM lionsClub where attrib not like '%XXXUP%'")
    result = await db.execute(query)
    club_list = result.fetchall()
    return templates.TemplateResponse("admin/clubList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "club_list": club_list,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/editclub/{clubno}", response_class=HTMLResponse)
async def editclub(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM lionsClub where clubNo = :clubNo")
    result = await db.execute(query, {"clubNo": clubno})
    clubdtl = result.fetchone()
    clubdocs = await get_clubdocs(clubno, db)
    return templates.TemplateResponse("admin/clubDetail.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clubdtl": clubdtl, "clubdocs": clubdocs,
        "user_clubno": clubno, "user_region": request.session.get("user_Region")
    })


@app.get("/editclubdoc/{clubno}", response_class=HTMLResponse)
async def editclubdoc(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM lionsClub where clubNo = :clubNo")
    result = await db.execute(query, {"clubNo": clubno})
    clubdtl = result.fetchone()
    return templates.TemplateResponse("admin/clubDocs.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clubdtl": clubdtl,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.post("/updateclubdoc/{clubno}")
async def updateclubdoc(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4docs = {
        "clubNo": clubno, "docType": form_data.get("doctype"), "docTitle": form_data.get("title"),
        "cDocument": form_data.get("content"),
    }
    querys = text(f"SELECT * from lionsDoc where clubNo = :clubNo and docType = :docType")
    result = await db.execute(querys, data4docs)
    docresult = result.fetchone()
    if docresult:
        queryup = text(
            "UPDATE lionsDoc SET modDate = :timenow , attrib = :updattrib WHERE clubNo = :clubno and docType = :doctype")
        timenow = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.execute(queryup, {"timenow": timenow, "updattrib": "XXXUPXXXUP", "clubno": clubno,
                                   "doctype": form_data.get("doctype")})
    query = text(
        "INSERT INTO lionsDoc (clubNo,docType,docTitle,cDocument) values (:clubNo,:docType,:docTitle,:cDocument)")
    await db.execute(query, data4docs)
    await db.commit()
    return RedirectResponse(f"/editclub/{clubno}", status_code=303)


@app.get("/popup_doc/{docno}")
async def get_popup_content(docno: int, db: AsyncSession = Depends(get_db)):
    cdoc = await get_clubdoc(docno, db)
    if cdoc: return HTMLResponse(cdoc)


@app.get("/listnotice/{regionno}", response_class=HTMLResponse)
async def listnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM boardMessage where regionNo = :regionNo and attrib not like '%XXXUP%'")
    result = await db.execute(query, {"regionNo": regionno})
    noticelist = result.fetchall()
    return templates.TemplateResponse("board/noticeList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticelist,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/clubnoticeread/{messageno}", response_class=HTMLResponse)
async def clubnoticeread(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text(
        "select cm.messageTitle , lm.memberName , na.readYN, na.attendPlan ,na.modDate from clubboardMessage cm "
        "left join lionsMember lm on cm.clubNo = lm.clubNo "
        "left join noticeAndswer na on na.noticeNo = cm.messageNo and na.memberNo = lm.memberNo "
        "where cm.messageNo = :messageNo order by lm.clubSortNo ")
    result = await db.execute(query, {"messageNo": messageno})
    noticeread = result.fetchall()
    return templates.TemplateResponse("board/clubnoticeRead.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticeread,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/circlenoticeread/{messageno}", response_class=HTMLResponse)
async def circlenoticeread(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text(
        "select cm.messageTitle , lm.memberName , na.readYN, na.attendPlan ,na.modDate from circleboardMessage cm "
        "left join lionsMember lm on cm.clubNo = lm.clubNo "
        "left join noticeAndswer na on na.noticeNo = cm.messageNo and na.noticeType = 'CIRCLE' "
        "where cm.messageNo = :messageNo order by lm.clubSortNo ")
    result = await db.execute(query, {"messageNo": messageno})
    noticeread = result.fetchall()
    return templates.TemplateResponse("board/circlenoticeRead.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticeread,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/regionnoticeread/{messageno}", response_class=HTMLResponse)
async def regionnoticeread(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text(
        "SELECT bm.messageTitle,lc.clubNo,lc.clubName,lm.memberNo,lm.memberName,na.readYN, na.attendPlan,na.modDate FROM boardMessage bm "
        "LEFT JOIN lionsClub lc ON lc.regionNo = bm.regionNo "
        "LEFT JOIN lionsMember lm ON lm.clubNo = lc.clubNo "
        "LEFT JOIN noticeAndswer na on bm.messageNo = na.noticeNo and lm.memberNo = na.memberNo "
        "WHERE bm.messageNo = :messageNo ORDER BY lc.clubNo, lm.memberNo")
    result = await db.execute(query, {"messageNo": messageno})
    noticeread = result.fetchall()
    return templates.TemplateResponse("board/regionnoticeRead.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticeread,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/listanswer/{noiceno}/{noticetype}", response_class=HTMLResponse)
async def listanswer(request: Request, noticeno: int, noticetype: str, db: AsyncSession = Depends(get_db)):
    query = text("SELECT * FROM noticeAnswer where noticeNo = :noticeno and noticeType = :noticetype")
    result = await db.execute(query, {"noticeno": noticeno, "noticetype": noticetype})
    return result.fetchall()


@app.get("/listcirclenotice/{circleno}", response_class=HTMLResponse)
async def listcirclenotice(request: Request, circleno: int,db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM circleboardMessage where circleNo = :circleNo and attrib not like '%XXXUP%'")
    result = await db.execute(query, {"circleNo": circleno})
    noticelist = result.fetchall()
    query2 = text("SELECT circleName FROM lionsCircle where circleNo = :circleNo")
    result2 = await db.execute(query2, {"circleNo": circleno})
    circlename = result2.fetchone()
    return templates.TemplateResponse("board/circlenoticeList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticelist, "circlename":circlename[0],"circleno":circleno,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/listclubnotice/{clubno}", response_class=HTMLResponse)
async def listclubnotice(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM clubboardMessage where clubNo = :clubNo and attrib not like '%XXXUP%'")
    result = await db.execute(query, {"clubNo": clubno})
    noticelist = result.fetchall()
    return templates.TemplateResponse("board/clubnoticeList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "notices": noticelist,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/addnotice/{regionno}", response_class=HTMLResponse)
async def addnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    return templates.TemplateResponse("board/addnotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "from_date": now.strftime(fmt),
        "to_date": two_weeks.strftime(fmt)
    })


@app.get("/clubsms/{clubno}", response_class=HTMLResponse)
async def clubsms(request: Request, clubno: int):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    return templates.TemplateResponse("board/clubsms.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/membersms/{clubno}", response_class=HTMLResponse)
async def membersms(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    user_list = await get_clubmemberlist(clubno, db)
    return templates.TemplateResponse("board/membersms.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "user_list": user_list
    })


@app.get("/addclubnotice/{clubno}", response_class=HTMLResponse)
async def addclubnotice(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    return templates.TemplateResponse("board/addclubnotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "from_date": now.strftime(fmt),
        "to_date": two_weeks.strftime(fmt)
    })


@app.get("/addcirclenotice/{circleno}", response_class=HTMLResponse)
async def addcirclenotice(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    return templates.TemplateResponse("board/addcirclenotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "from_date": now.strftime(fmt),
        "to_date": two_weeks.strftime(fmt), "circleno": circleno
    })


@app.get("/editnotice/{messageno}", response_class=HTMLResponse)
async def editnotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM boardMessage where messageNo = :messageno")
    result = await db.execute(query, {"messageno": messageno})
    notice = result.fetchone()
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    from_date = notice[6] if notice[6] is not None else now.strftime(fmt)
    to_date = notice[7] if notice[7] is not None else two_weeks.strftime(fmt)
    return templates.TemplateResponse("board/editnotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "notice": notice, "from_date": from_date, "to_date": to_date
    })


@app.get("/editclubnotice/{messageno}", response_class=HTMLResponse)
async def editclubnotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM clubboardMessage where messageNo = :messageno")
    result = await db.execute(query, {"messageno": messageno})
    notice = result.fetchone()
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    from_date = notice[6] if notice[6] is not None else now.strftime(fmt)
    to_date = notice[7] if notice[7] is not None else two_weeks.strftime(fmt)
    return templates.TemplateResponse("board/editclubnotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "notice": notice, "from_date": from_date, "to_date": to_date
    })


@app.get("/editcirclenotice/{messageno}", response_class=HTMLResponse)
async def editcirclenotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM circleboardMessage where messageNo = :messageno")
    result = await db.execute(query, {"messageno": messageno})
    notice = result.fetchone()
    now = datetime.datetime.now()
    two_weeks = now + datetime.timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    from_date = notice[6] if notice[6] is not None else now.strftime(fmt)
    to_date = notice[7] if notice[7] is not None else two_weeks.strftime(fmt)
    return templates.TemplateResponse("board/editcirclenotice.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "user_region": request.session.get("user_Region"),
        "user_clubno": request.session.get("user_Clubno"), "notice": notice, "from_date": from_date, "to_date": to_date
    })


@app.post("/updatecirclemember/{cmid}", response_class=HTMLResponse)
async def update_ccirclemember(request: Request, cmid: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "circleNo": form_data.get("circleno"), "memberNo": form_data.get("memberno"),
        "rankNo": form_data.get("rankno"), "addRemark": form_data.get("memo"),
    }
    circleno = form_data.get("circleno")
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE circleMember SET {set_clause} WHERE cmId = :cmid")
    update_fields["cmid"] = cmid
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/circlememberList/{circleno}", status_code=303)


@app.post("/updatenotice/{messageno}", response_class=HTMLResponse)
async def updatenotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE boardMessage SET {set_clause} WHERE messageNo = :messageNo")
    update_fields["messageNo"] = messageno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/listnotice/{request.session.get('user_Region')}", status_code=303)


@app.post("/updateclubnotice/{messageno}", response_class=HTMLResponse)
async def update_clubnot(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE clubboardMessage SET {set_clause} WHERE messageNo = :messageNo")
    update_fields["messageNo"] = messageno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/listclubnotice/{request.session.get('user_Clubno')}", status_code=303)


@app.post("/updatecirclenotice/{messageno}", response_class=HTMLResponse)
async def update_circlenot(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE circleboardMessage SET {set_clause} WHERE messageNo = :messageNo")
    update_fields["messageNo"] = messageno
    await db.execute(query, update_fields)
    await db.commit()
    query2 = text("SELECT circleNo FROM circleboardMessage where messageNo = :messageNo")
    result2 = await db.execute(query2, {"messageNo": messageno})
    circleno = result2.fetchone()[0]
    return RedirectResponse(f"/listcirclenotice/{circleno}", status_code=303)


@app.post("/removenotice/{messageno}", response_class=HTMLResponse)
async def removenotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"UPDATE boardMessage SET attrib = :XXUP WHERE messageNo = :messageNo")
    await db.execute(query, {"XXUP": "XXXUPXXXUP", "messageNo": messageno})
    await db.commit()
    return RedirectResponse(f"/listnotice/{request.session.get('user_Region')}", status_code=303)


@app.post("/removeclubnotice/{messageno}", response_class=HTMLResponse)
async def removeclubnotice(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"UPDATE clubboardMessage SET attrib = :XXUP WHERE messageNo = :messageNo")
    await db.execute(query, {"XXUP": "XXXUPXXXUP", "messageNo": messageno})
    await db.commit()
    return RedirectResponse(f"/listclubnotice/{request.session.get('user_Clubno')}", status_code=303)


@app.post("/removecirclenotice/{messageno}/{circleno}", response_class=HTMLResponse)
async def removecirclenotice(request: Request, messageno: int,circleno:int,db: AsyncSession = Depends(get_db)):
    query = text(f"UPDATE circleboardMessage SET attrib = :XXUP WHERE messageNo = :messageNo")
    await db.execute(query, {"XXUP": "XXXUPXXXUP", "messageNo": messageno})
    await db.commit()
    query2 = text(f"Select circleName from lionsCircle where circleNo = :circleNo")
    result = await db.execute(query2, {"circleNo": circleno})
    circlename = result.fetchone()
    return RedirectResponse(f"/listcirclenotice/{circleno}", status_code=303)


@app.post("/insertnotice/{regionno}", response_class=HTMLResponse)
async def insertnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4insert = {
        "regionNo": regionno, "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    insert_fields = {key: value for key, value in data4insert.items() if value is not None}
    columns = ", ".join(insert_fields.keys())
    values = ", ".join([f":{key}" for key in insert_fields.keys()])
    query = text(f"INSERT INTO boardMessage ({columns}) VALUES ({values})")
    await db.execute(query, insert_fields)
    await db.commit()
    await send_fcm_topic_notice_region(regionno=regionno, title="새로운 지역 공지사항", body=form_data.get("nottitle") or "지역공지")
    return RedirectResponse(f"/listnotice/{request.session.get('user_Region')}", status_code=303)


@app.post("/insertclubnotice/{clubno}", response_class=HTMLResponse)
async def insertclubnotice(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4insert = {
        "clubNo": clubno, "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    insert_fields = {key: value for key, value in data4insert.items() if value is not None}
    columns = ", ".join(insert_fields.keys())
    values = ", ".join([f":{key}" for key in insert_fields.keys()])
    query = text(f"INSERT INTO clubboardMessage ({columns}) VALUES ({values})")
    await db.execute(query, insert_fields)
    await db.commit()
    await send_fcm_topic_notice(clubno=clubno, title="새로운 클럽 공지사항", body=form_data.get("nottitle") or "클럽공지")
    return RedirectResponse(f"/listclubnotice/{request.session.get('user_Clubno')}", status_code=303)


@app.post("/insertcirclenotice/{circleno}", response_class=HTMLResponse)
async def insertcirclenotice(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4insert = {
        "circleNo": circleno, "messageTitle": form_data.get("nottitle"), "MessageConts": form_data.get("notmessage"),
        "MessageType": form_data.get("nottype"), "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    insert_fields = {key: value for key, value in data4insert.items() if value is not None}
    columns = ", ".join(insert_fields.keys())
    values = ", ".join([f":{key}" for key in insert_fields.keys()])
    query = text(f"INSERT INTO circleboardMessage ({columns}) VALUES ({values})")
    await db.execute(query, insert_fields)
    await db.commit()
    query2 = text(f"Select circleName from lionsCircle where circleNo = :circleNo")
    result = await db.execute(query2, {"circleNo": circleno})
    circlename = result.fetchone()
#    await send_fcm_topic_notice(circleno=circleno, title="새로운 써클 공지사항", body=form_data.get("nottitle") or "써클공지")
    return RedirectResponse(f"/listcirclenotice/{circleno}", status_code=303)

@app.post("/sendclubsms/{clubno}", response_class=HTMLResponse)
async def sendclubsms(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    await send_fcm_topic_notice(clubno=clubno, title=form_data.get("smstitle") or "클럽공지",
                                body=form_data.get("smsmessage") or "클럽공지")
    return RedirectResponse(f"/clubsms/{request.session.get('user_Clubno')}", status_code=303)


@app.post("/sendmembersms/{clubno}", response_class=HTMLResponse)
async def sendmembersms(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    smstitle = form_data.get("smstitle")
    smsmessage = form_data.get("smsmessage")
    selusers = form_data.getlist("seluser")
    for memberno in selusers:
        await send_fcm_topic_notice_member(memberno=memberno, title=smstitle or "개별통지", body=smsmessage or "개별통지")
    return RedirectResponse(f"/membersms/{request.session.get('user_Clubno')}", status_code=303)


@app.post("/updateclub/{clubno}", response_class=HTMLResponse)
async def updateclub(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "clubName": form_data.get("clubname"), "estDate": form_data.get("estdate"), "regionNo": form_data.get("regno"),
        "officeAddr": form_data.get("offaddr"), "officeTel": form_data.get("offtel"),
        "officeFax": form_data.get("offfax"),
        "officeEmail": form_data.get("offemail"), "officeWeb": form_data.get("offweb"),
        "modDate": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE lionsClub SET {set_clause} WHERE clubNo = :clubNo")
    update_fields["clubNo"] = clubno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/editclub/{clubno}", status_code=303)


@app.post("/updatecircle/{circleno}", response_class=HTMLResponse)
async def updatecircle(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "circleName": form_data.get("circlename"), "circleType": form_data.get("circletype"),
        "circleAddress": form_data.get("circleaddr"), "circleTel": form_data.get("circletel"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE lionsCircle SET {set_clause} WHERE circleNo = :circleNo")
    update_fields["circleNo"] = circleno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/editcircle/{circleno}", status_code=303)


@app.get("/regionclubList/{regno}", response_class=HTMLResponse)
async def regionclubList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    club_list = await get_regionclublist(regno, db)
    return templates.TemplateResponse("member/regionclubList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "club_list": club_list,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/rankList", response_class=HTMLResponse)
async def rankList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    rank_list = await get_ranklistall(db)
    return templates.TemplateResponse("admin/rankList.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "rank_list": rank_list,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/rankDetail/{rankno}", response_class=HTMLResponse)
async def rankDetail(request: Request, rankno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    rank_dtl = await get_rankdtl(rankno, db)
    return templates.TemplateResponse("admin/rankDetail.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "rank_dtl": rank_dtl,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.post("/update_rank/{rankno}", response_class=HTMLResponse)
async def update_rank(request: Request, rankno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "rankNo": rankno, "rankTitlekor": form_data.get("rankkor"), "rankTitleeng": form_data.get("rankeng"),
        "rankDiv": form_data.get("ranktype"), "orderNo": form_data.get("orderno"), "useYN": form_data.get("useyn"),
    }
    query = text(
        "UPDATE lionsRank SET rankTitlekor = :rankTitlekor, rankTitleeng = :rankTitleeng, rankDiv = :rankDiv, orderNo = :orderNo, useYN = :useYN WHERE rankNo = :rankNo")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/rankDetail/{rankno}", status_code=303)


@app.get("/add_rank", response_class=HTMLResponse)
async def add_rank(request: Request, db: AsyncSession = Depends(get_db)):
    query = text(
        "INSERT INTO lionsRank (rankTitlekor, rankTitleeng, rankDiv, orderNo) values (:rankTitlekor, :rankTitleeng, :rankDiv, :orderNo)")
    await db.execute(query,
                     {"rankTitlekor": "새로 등록된 직책", "rankTitleeng": "New Rank", "rankDiv": "CLUB", "orderNo": "0"})
    await db.commit()
    return RedirectResponse(f"/rankList", status_code=303)


@app.get("/editregion/{regno}", response_class=HTMLResponse)
async def editregion(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM lionsRegion where regionNo = :regNo and attrib not like :atts")
    result = await db.execute(query, {"regNo": regno, "atts": "%XXX%"})
    regiondtl = result.fetchone()
    rankmembers = await get_rankmemberlist(15, db)
    return templates.TemplateResponse("admin/regionDetail.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "regiondtl": regiondtl, "rankmembers": rankmembers,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.get("/editbis/{memberno}", response_class=HTMLResponse)
async def editbis(request: Request, memberno: int, saved: int = 0, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    query = text("SELECT * FROM memberBusiness where memberNo = :memberno and attrib not like :atts")
    result = await db.execute(query, {"memberno": memberno, "atts": "%XXX%"})
    bisdtl = result.fetchone()
    return templates.TemplateResponse("business/regBis.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "memberno": memberno,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno"),
        "saved": saved, "bisdtl": bisdtl
    })


@app.post("/update_business/{memberno}", response_class=HTMLResponse)
async def update_bisdtl(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "dt1": memberno, "dt2": form_data.get("bistitle"), "dt3": form_data.get("bisrank"),
        "dt4": form_data.get("bistype"), "dt5": form_data.get("bistypedtl"), "dt6": form_data.get("offtel"),
        "dt7": form_data.get("offaddress"), "dt8": form_data.get("offemail"), "dt9": form_data.get("offpost"),
        "dt10": form_data.get("offweb"), "dt11": form_data.get("offsns"), "dt12": form_data.get("offmemo")
    }
    queryup = text(f"UPDATE memberBusiness SET attrib = :attr WHERE memberNo = :memberno")
    await db.execute(queryup, {"memberno": memberno, "attr": "XXXUPXXXUP"})
    query = text("INSERT INTO memberBusiness (memberNo,bisTitle, bisRank, bisType,bistypeTitle,officeTel,officeAddress,officeEmail,officePostNo,officeWeb,officeSns,bisMemo) values (:dt1,:dt2,:dt3,:dt4,:dt5,:dt6,:dt7,:dt8,:dt9,:dt10,:dt11,:dt12)")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(url=f"/editbis/{memberno}?saved=1", status_code=303)


@app.post("/updateregion/{regno}", response_class=HTMLResponse)
async def update_regdtl(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "regionNo": form_data.get("regno"), "chairmanNo": form_data.get("chairmno"),
        "regionSlog": form_data.get("slog"), "yearFrom": form_data.get("yearfrom"), "yearTo": form_data.get("yearto"),
    }
    mdatenow = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    queryup = text(f"UPDATE lionsRegion SET attrib = :attr, modDate = :mdate WHERE regionNo = :regno")
    await db.execute(queryup, {"regno": regno, "attr": "XXXUPXXXUP", "mdate": mdatenow})
    query = text("INSERT INTO lionsRegion (regionNo,chairmanNo,regionSlog,yearFrom,yearTo) values (:regionNo,:chairmanNo,:regionSlog, :yearFrom, :yearTo)")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/editregion/{regno}", status_code=303)


@app.get("/boardManager/{regionno}", response_class=HTMLResponse)
async def boardManager(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    clublist = await get_regionboardlist(regionno, db)
    return templates.TemplateResponse("board/boardMain.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clublist": clublist,
        "user_Region": request.session.get("user_Region"), "user_Clubno": request.session.get("user_Clubno")
    })


@app.get("/boardList/{clubno}/{clubname}", response_class=HTMLResponse)
async def clubboardlist(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    clubboards = await get_clubboards(clubno, db)
    return templates.TemplateResponse("board/clubboardlist.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "clubboards": clubboards, "clubname": clubname,
        "user_clubno": clubno, "user_region": request.session.get("user_Region")
    })


@app.get("/editboard/{boardno}/{clubname}", response_class=HTMLResponse)
async def editboard(request: Request, boardno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    boarddtl = await get_boarddtl(boardno, db)
    return templates.TemplateResponse("board/editboard.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "boarddtl": boarddtl, "clubname": clubname,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.api_route("/addboard/{clubno}", response_class=HTMLResponse, methods=["GET", "POST"])
async def addboard(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    btitle = form_data.get("btitle") or "새로 만든 게시판(제목 변경 필요)"
    btype = form_data.get("btype") or "BOARD"
    query = text(f"INSERT into lionsBoard (clubNo, boardTitle, boardType) values (:clubNo, :boardTitle, :boardType)")
    await db.execute(query, {"clubNo": clubno, "boardTitle": btitle, "boardType": btype})
    await db.commit()
    return RedirectResponse(f"/boardList/{clubno}", status_code=303)


@app.get("/requestList", response_class=HTMLResponse)
async def requestlist(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    if not user_No: return RedirectResponse(url="/")
    requests = await get_requests(db)
    return templates.TemplateResponse("board/requestlist.html", {
        "request": request, "user_No": user_No, "user_Name": request.session.get("user_Name"),
        "user_Role": request.session.get("user_Role"), "requests": requests,
        "user_region": request.session.get("user_Region"), "user_clubno": request.session.get("user_Clubno")
    })


@app.post("/updaterequest/{requestno}")
async def updaterequest(request: Request, requestno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"UPDATE requestMessage SET attrib = :attr WHERE requestNo = :requestno")
    await db.execute(query, {"requestno": requestno, "attr": "XXXUPXXXUP"})
    await db.commit()
    return JSONResponse({"result": "ok"})


@app.post("/membertocircle/{circleno}/{memberno}")
async def membertocircle(request: Request, circleno: int, memberno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"select * from circleMember where circleNo = :circleno and memberNo = :memberno")
    result = await db.execute(query, {"circleno": circleno, "memberno": memberno})
    if result.rowcount == 0:
        query = text(f"INSERT into circleMember (circleNo, memberNo) values (:circleno, :memberno)")
        await db.execute(query, {"circleno": circleno, "memberno": memberno})
        await db.commit()
        return JSONResponse({"result": "ok"})
    else:
        return JSONResponse({"result": "already"})


@app.post("/membertocircleminus/{circleno}/{memberno}")
async def membertocircleminus(request: Request, circleno: int, memberno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"select * from circleMember where circleNo = :circleno and memberNo = :memberno")
    result = await db.execute(query, {"circleno": circleno, "memberno": memberno})
    if result.rowcount != 0:
        query = text(f"DELETE FROM circleMember where circleNo = :circleno and memberNo = :memberno")
        await db.execute(query, {"circleno": circleno, "memberno": memberno})
        await db.commit()
        return JSONResponse({"result": "ok"})
    else:
        return JSONResponse({"result": "already"})


@app.get("/slimage/{clubno}")
async def slogan_image(clubno: int, db: AsyncSession = Depends(get_db)):
    staff = await get_clubstaffwithname(clubno, db)
    slogan = staff[1] if staff else "No Slogan"
    memberno = staff[2] if staff else 0
    name = staff[3]+"L" if staff else "No Name"
    sub1 = staff[4] if staff else 0
    sub1n = staff[5]+"L" if staff else "No Name"
    sub2 = staff[6] if staff else 0
    sub2n = staff[7]+"L" if staff else "No Name"
    sub_members = [(sub1, sub1n), (sub2, sub2n)]
    img = make_slogan_image(slogan, memberno, name, width=400, height=520, sub_members=sub_members)
    save_dir = "./static/img/members"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{clubno}logo.png")
    img.save(save_path, format="PNG")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/slimage_circle/{circleno}")
async def cirslogan_image(circleno: int, db: AsyncSession = Depends(get_db)):
    staff = await get_circlestaffwithname(circleno, db)

    slogan = staff[1] if staff else "No Slogan"
    memberno = staff[3] if staff else 0
    name = str(staff[4]) + "L" if staff and len(staff) > 3 and staff[3] is not None else "No Name"

    sub1 = staff[5] if staff and len(staff) > 4 else 0
    sub1n = str(staff[6]) + "L" if staff and len(staff) > 5 and staff[5] is not None else "No Name"

    sub2 = staff[7] if staff and len(staff) > 6 else 0
    sub2n = str(staff[8]) + "L" if staff and len(staff) > 7 and staff[7] is not None else "No Name"

    sub_members = [(sub1, sub1n), (sub2, sub2n)]
    img = make_slogan_image(slogan, memberno, name, width=400, height=520, sub_members=sub_members)

    save_dir = "./static/img/members"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{circleno}circlelogo.png")
    img.save(save_path, format="PNG")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.api_route("/updateboard/{boardno}/{clubno}/{clubname}", response_class=HTMLResponse, methods=["GET", "POST"])
async def updateboard(request: Request, boardno: int, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    btitle = form_data.get("btitle")
    btype = form_data.get("btype")
    query = text(f"update lionsBoard set boardTitle=:boardTitle,boardType=:boardType where boardNo=:boardNo")
    await db.execute(query, {"boardNo": boardno, "boardTitle": btitle, "boardType": btype})
    await db.commit()
    return RedirectResponse(f"/boardList/{clubno}/{clubname}", status_code=303)


@app.api_route("/updateclubsort/{memberno}/{sortno}", response_class=HTMLResponse, methods=["GET", "POST"])
async def updatesort(request: Request, memberno: int, sortno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"update lionsMember set clubSortNo=:sortNo where memberNo=:memberNo")
    await db.execute(query, {"sortNo": sortno, "memberNo": memberno})
    await db.commit()
    return JSONResponse(content={"result": "ok"})


@app.get("/clubStaff/{clubno}/{clubName}", response_class=HTMLResponse)
async def clubstaff(request: Request, clubno: int, clubName: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    staff_dtl = await get_clubstaff(clubno, db)
    clubmember = await get_clubmemberlist(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubStaff.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,"user_Role": user_Role,
                                       "clubName": clubName, "clubno": clubno,
                                       "staff_dtl": staff_dtl, "clubmember": clubmember, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/circleStaff/{circleno}", response_class=HTMLResponse)
async def circlestaff(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    circlestaff = await get_circlestaffwithname(circleno, db)
    circlembrlist = await get_circlememberlist(circleno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/circleStaff.html", {"request": request, "user_No": user_No, "user_Name": user_Name,"user_Role": user_Role,"circle_no":circleno,
                                       "user_region": user_region, "user_clubno": user_clubno, "circlembrlist": circlembrlist, "circlestaff": circlestaff})


@app.post("/updatestaff/{clubno}", response_class=HTMLResponse)
async def update_stff(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    clubName = form_data.get("clubname")
    data4update = {
        "logPeriod": form_data.get("dutyyear"),
        "clubNo": clubno,
        "presidentNo": form_data.get("presno"),
        "secretNo": form_data.get("secrno"),
        "trNo": form_data.get("trsuno"),
        "ltNo": form_data.get("ltno"),
        "ttNo": form_data.get("ttno"),
        "prpresidentNo": form_data.get("ppresno"),
        "firstViceNo": form_data.get("fviceno"),
        "secondViceNo": form_data.get("sviceno"),
        "thirdViceNo": form_data.get("tviceno"),
        "slog": form_data.get("slog"),
    }
    queryb = text(f"UPDATE lionsClubstaff set attrib = :attrib WHERE clubNo = :clubNo")
    await db.execute(queryb, {"attrib": 'XXXUPXXXUP', "clubNo": clubno})
    query = text(
        f"INSERT INTO lionsClubstaff (logPeriod,clubNo,presidentNo,secretNo,trNo,ltNo,ttNo,prpresidentNo,firstViceNo,secondViceNo,thirdViceNo,slog) values (:logPeriod,:clubNo,:presidentNo,:secretNo,:trNo,:ltNo,:ttNo,:prpresidentNo,:firstViceNo,:secondViceNo,:thirdViceNo,:slog)")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/clubStaff/{clubno}/{clubName}", status_code=303)


@app.post("/updatecirclestaff/{circleno}", response_class=HTMLResponse)
async def update_stff(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    raw_data = {
        "logPeriod": form_data.get("dutyyear"),
        "circleNo": circleno,
        "presidentNo": form_data.get("presno"),
        "secretNo": form_data.get("secrno"),
        "trNo": form_data.get("trsuno"),
        "ltNo": form_data.get("ltno"),
        "ttNo": form_data.get("ttno"),
        "prpresidentNo": form_data.get("ppresno"),
        "firstViceNo": form_data.get("fviceno"),
        "secondViceNo": form_data.get("sviceno"),
        "thirdViceNo": form_data.get("tviceno"),
        "slog": form_data.get("slog"),
    }
    data4update = {
        key: value for key, value in raw_data.items()
        if value is not None and str(value).strip() != ""
    }
    queryb = text("UPDATE lionsCirclestaff SET attrib = :attrib WHERE circleNo = :circleNo")
    await db.execute(queryb, {"attrib": 'XXXUPXXXUP', "circleNo": circleno})
    columns = ", ".join(data4update.keys())
    placeholders = ", ".join([f":{key}" for key in data4update.keys()])
    insert_query_str = f"INSERT INTO lionsCirclestaff ({columns}) VALUES ({placeholders})"
    query = text(insert_query_str)
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/circleStaff/{circleno}", status_code=303)


@app.get("/circleList", response_class=HTMLResponse)
async def circleList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    circle_list = await get_circlelist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/circleList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,"user_Role": user_Role,
                                       "circle_list": circle_list, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/editcircle/{circleno}", response_class=HTMLResponse)
async def editcircle(request: Request, circleno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM lionsCircle where circleNo = :circleNo and attrib not like :atts")
    result = await db.execute(query, {"circleNo": circleno, "atts": "%XXX%"})
    circledtl = result.fetchone()
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/circleDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,"user_Role": user_Role,
                                       "circledtl": circledtl, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/regionList", response_class=HTMLResponse)
async def dictList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    region_list = await get_regionlist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/regionList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,"user_Role": user_Role,
                                       "region_list": region_list, "user_region": user_region, "user_clubno": user_clubno})




@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


class RequestMessage(BaseModel):
    memberNo: str
    message: str

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy/privacy.htm", {"request": request})

@app.get("/privacy2", response_class=HTMLResponse)
async def privacy2(request: Request):
    return templates.TemplateResponse("privacy/privacy.htm", {"request": request})


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "/error/errorInfo.html",
            {"request": request, "error_message": "페이지를 찾을 수 없습니다."},
            status_code=404,
        )
    if exc.status_code == 500:
        return templates.TemplateResponse(
            "/error/errorInfo.html",
            {"request": request, "error_message": "시스템 내부 에러 발생."},
            status_code=500,
        )
    return HTMLResponse(
        content=f"<h1>{exc.status_code} - {exc.detail}</h1>",
        status_code=exc.status_code,
    )

@app.get("/contactus", response_class=HTMLResponse)
async def contactus(request: Request):
    return templates.TemplateResponse("help/contactus.html", {"request": request})

# ==========================================
# 모바일 앱 라우터 등록 (순환 참조 방지를 위해 맨 아래에 위치)
# ==========================================
from phapphub import phapp_router
app.include_router(phapp_router)