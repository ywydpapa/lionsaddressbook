from urllib import request
import uvicorn
from fastapi import FastAPI, Depends, Request, Form, Response, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pycparser.ply.yacc import resultlimit
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
import dotenv
import os
import base64
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw
import io
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from io import BytesIO

from starlette.responses import FileResponse

dotenv.load_dotenv()
DATABASE_URL = os.getenv("dburl")
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="supersecretkey")
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
THUMBNAIL_DIR = "./static/img/members"


# 데이터베이스 세션 생성
async def get_db():
    async with async_session() as session:
        yield session


# 썸네일 생성 함수
async def save_thumbnail(image_data: bytes, memberno: int, size=(100, 100)):
    # 디렉토리가 없으면 생성
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    # 원본 이미지를 Pillow로 열기
    image = Image.open(io.BytesIO(image_data))
    # 썸네일 생성
    image.thumbnail(size)
    # 저장 경로
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{memberno}.png")
    # 썸네일 저장
    image.save(thumbnail_path, format="PNG")
    return thumbnail_path


async def save_ncthumbnail(image_data: bytes, memberno: int, size=(80, 100)):
    # 디렉토리가 없으면 생성
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    # 원본 이미지를 Pillow로 열기
    image = Image.open(io.BytesIO(image_data))
    # 썸네일 생성
    image.thumbnail(size)
    # 저장 경로
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"nc{memberno}.png")
    # 썸네일 저장
    image.save(thumbnail_path, format="PNG")
    return thumbnail_path


async def get_clublist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClub where attrib not like :attpatt")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return club_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBLIST)")


async def get_clubboards(clubno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsBoard where attrib not like :attpatt AND clubno = :clubno")
        result = await db.execute(query, {"attpatt": "%XXX%", "clubno": clubno})
        clubboards = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return clubboards
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBBOARDS)")


def get_default_image_base64(mime_type: str = "image/png") -> str:
    default_image_path = "static/img/defaultphoto.png"
    try:
        with open(default_image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_image}"
    except FileNotFoundError:
        raise Exception("Default image file not found.")


async def get_photo(memberNo: int, db: AsyncSession, mime_type: str = "image/jpeg") -> str:
    try:
        query = text("SELECT mPhoto FROM memberPhoto WHERE memberNo = :memberNo order by regDate desc")
        result = await db.execute(query, {"memberNo": memberNo})
        photo = result.fetchone()
        if photo is None:
            return get_default_image_base64(mime_type)
        base64_image = base64.b64encode(photo[0]).decode("utf-8")
        return f"data:{mime_type};base64,{base64_image}"
    except:
        raise HTTPException(status_code=500, detail="Database query failed(Photo)")


async def get_spphoto(memberNo: int, db: AsyncSession, mime_type: str = "image/jpeg") -> str:
    try:
        query = text("SELECT spousePhoto FROM memberSpouse WHERE memberNo = :memberNo order by regDate desc")
        result = await db.execute(query, {"memberNo": memberNo})
        photo = result.fetchone()
        if photo is None:
            return get_default_image_base64(mime_type)
        base64_image = base64.b64encode(photo[0]).decode("utf-8")
        return f"data:{mime_type};base64,{base64_image}"
    except:
        raise HTTPException(status_code=500, detail="Database query failed(Photo)")


async def get_namecard(memberNo: int, db: AsyncSession, mime_type: str = "image/jpeg") -> str:
    try:
        query = text("SELECT ncardPhoto FROM memberNamecard WHERE memberNo = :memberNo order by regDate desc")
        result = await db.execute(query, {"memberNo": memberNo})
        photo = result.fetchone()
        if photo is None:
            return get_default_image_base64(mime_type)
        base64_image = base64.b64encode(photo[0]).decode("utf-8")
        return f"data:{mime_type};base64,{base64_image}"
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


async def get_regionboardlist(region: int, db: AsyncSession):
    try:
        query = text(
            "select lc.clubName , lb.clubNo, GROUP_CONCAT(lb.boardTitle SEPARATOR ',') AS boardDetails, count(lb.boardNo ) from lionsBoard lb "
            "left join lionsClub lc on lb.clubNo = lc.clubNo and lc.regionNo = :regno  group by lb.clubNo order by lb.clubNo")
        result = await db.execute(query, {"regno": region})
        club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return club_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")


async def get_regionmemberlist(region: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lcc.clubName, lr.rankTitlekor FROM lionsMember lm left join lionsClub lcc on lm.clubNo = lcc.clubNo "
            "left join lionsRank lr on lm.rankNo = lr.rankNo where lm.clubNo in (select lc.clubno from lionsClub lc where lc.regionNo = :regno) order by lm.clubNo, lm.memberJoindate")
        result = await db.execute(query, {"regno": region})
        rmember_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return rmember_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")


async def get_memberlist(db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lcc.clubName, lr.rankTitlekor FROM lionsMember lm left join lionsClub lcc on lm.clubNo = lcc.clubNo "
            "left join lionsRank lr on lm.rankNo = lr.rankNo")
        result = await db.execute(query)
        member_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return member_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(MEMBERLIST)")


async def get_rankmemberlist(rankno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsMember where rankNo = :rankno")
        result = await db.execute(query, {"rankno": rankno})
        rankmember_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return rankmember_list
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


async def get_clubmembercard(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lr.rankTitlekor FROM lionsMember lm LEFT join lionsRank lr on lm.rankNo = lr.rankNo where clubNo = :club_no")
        result = await db.execute(query, {"club_no": clubno})
        member_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        member = [
            {
                "memberNo": row.memberNo,
                "memberName": row.memberName,
                "memberPhone": row.memberPhone,
                "memberEmail": row.memberEmail,
                "memberMF": row.memberMF,
                "rankTitle": row.rankTitlekor,
            }
            for row in member_list
        ]
        return {"members": member}
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBMemberCards)")


async def get_clubmemberlist(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lr.rankTitlekor FROM lionsMember lm LEFT join lionsRank lr on lm.rankNo = lr.rankNo where clubNo = :club_no")
        result = await db.execute(query, {"club_no": clubno})
        member_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return member_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBMemberList)")


async def get_clubdocs(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT * FROM lionsDoc where clubNo = :clubno and attrib not like :attrxx")
        result = await db.execute(query, {"clubno": clubno, "attrxx": '%XXX%'})
        doc_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return doc_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBDocList)")


async def get_clubdoc(docno: int, db: AsyncSession):
    try:
        query = text("SELECT cDocument from lionsDoc where docno = :docno")
        result = await db.execute(query, {"docno": docno})
        doc = result.fetchone()
        return doc[0]
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBDoc)")


async def get_regionlist(db: AsyncSession):
    try:
        query = text(
            "SELECT lr.*, GROUP_CONCAT(lc.clubName SEPARATOR ', ') AS clubNames, lm.memberName FROM lionsaddr.lionsRegion lr "
            "LEFT JOIN lionsaddr.lionsClub lc ON lr.regionNo = lc.regionNo "
            "LEFT JOIN lionsaddr.lionsMember lm ON lr.chairmanNo = lm.memberNo "
            "where lr.attrib not like :attpatt GROUP BY lr.regionNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        dict_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return dict_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(DICT)")


async def get_clubstaff(clubno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClubstaff where clubNo = :clubno and attrib not like :attrxx")
        result = await db.execute(query, {"clubno": clubno, "attrxx": '%XXX%'})
        staff_list = result.fetchone()
        return staff_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBSTAFF)")


async def get_clubstaffwithname(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT s.logPeriod, s.slog, "
            "s.presidentNo, COALESCE(pm.memberName, '공석') AS presidentName, "
            "s.secretNo, COALESCE(sm.memberName, '공석') AS secretName, "
            "s.trNo, COALESCE(tm.memberName, '공석') AS trName, "
            "s.ltNo, COALESCE(ltm.memberName, '공석') AS ltName, "
            "s.ttNo, COALESCE(ttm.memberName, '공석') AS ttName, "
            "s.prpresidentNo, COALESCE(prm.memberName, '공석') AS prpresidentName, "
            "s.firstViceNo, COALESCE(fvm.memberName, '공석') AS firstViceName, "
            "s.secondViceNo, COALESCE(svm.memberName, '공석') AS secondViceName, "
            "s.thirdViceNo, COALESCE(tvm.memberName, '공석') AS thirdViceName "
            "FROM lionsClubstaff s "
            "LEFT JOIN lionsMember pm ON s.presidentNo = pm.memberNo "
            "LEFT JOIN lionsMember sm ON s.secretNo = sm.memberNo "
            "LEFT JOIN lionsMember tm ON s.trNo = tm.memberNo "
            "LEFT JOIN lionsMember ltm ON s.ltNo = ltm.memberNo "
            "LEFT JOIN lionsMember ttm ON s.ttNo = ttm.memberNo "
            "LEFT JOIN lionsMember prm ON s.prpresidentNo = prm.memberNo "
            "LEFT JOIN lionsMember fvm ON s.firstViceNo = fvm.memberNo "
            "LEFT JOIN lionsMember svm ON s.secondViceNo = svm.memberNo "
            "LEFT JOIN lionsMember tvm ON s.thirdViceNo = tvm.memberNo "
            "WHERE s.clubNo = :clubno and s.attrib not like :attrxx")
        result = await db.execute(query, {"clubno": clubno, "attrxx": '%XXX%'})
        staff_list = result.fetchone()
        return staff_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBSTAFFWNAME)")


def make_slogan_image(slogan: str, member_no: int, name: str, width=400, height=400, font_size=20,
                      sub_members=[(2, "서브1"), (3, "서브2")]) -> Image.Image:
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("NanumGothic.ttf", font_size)
        name_font = ImageFont.truetype("NanumGothic.ttf", 18)
    except:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # 1. 슬로건
    bbox = draw.textbbox((0, 0), slogan, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    y = 20
    draw.text((x, y), slogan, fill="black", font=font)

    # 2. 메인 프로필(상단 중앙)
    rect_w, rect_h = 80, 100
    rect_x = (width - rect_w) // 2
    rect_y = y + bbox[3] + 20
    draw.rectangle([rect_x, rect_y, rect_x + rect_w, rect_y + rect_h], outline="gray", width=2)
    try:
        profile_img = Image.open(f"./static/img/members/{member_no}.png").resize((rect_w, rect_h))
        img.paste(profile_img, (rect_x, rect_y))
    except Exception as e:
        pass
    # 이름 사각형(중앙)
    name_rect_w, name_rect_h = 80, 30
    name_rect_x = (width - name_rect_w) // 2
    name_rect_y = rect_y + rect_h + 5
    draw.rectangle([name_rect_x, name_rect_y, name_rect_x + name_rect_w, name_rect_y + name_rect_h], outline="gray", width=2)
    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    name_text_w = name_bbox[2] - name_bbox[0]
    name_text_h = name_bbox[3] - name_bbox[1]
    name_x = name_rect_x + (name_rect_w - name_text_w) // 2
    name_y = name_rect_y + (name_rect_h - name_text_h) // 2 - name_bbox[1]
    draw.text((name_x, name_y), name, fill="black", font=name_font)

    # 3. 하단 2개 프로필(좌우 균등)
    sub_rect_w, sub_rect_h = 80, 100
    sub_name_rect_h = 30
    gap = (width - 2*sub_rect_w) // 3  # 좌-중앙-우 간격

    for i, (sub_no, sub_name) in enumerate(sub_members):
        # 프로필 사각형
        sub_rect_x = gap + i * (sub_rect_w + gap)
        sub_rect_y = name_rect_y + name_rect_h + 20  # 상단 이름박스 아래 20px
        draw.rectangle([sub_rect_x, sub_rect_y, sub_rect_x + sub_rect_w, sub_rect_y + sub_rect_h], outline="gray", width=2)
        try:
            sub_img = Image.open(f"./static/img/members/{sub_no}.png").resize((sub_rect_w, sub_rect_h))
            img.paste(sub_img, (sub_rect_x, sub_rect_y))
        except Exception as e:
            pass
        # 이름 사각형
        sub_name_rect_x = sub_rect_x
        sub_name_rect_y = sub_rect_y + sub_rect_h + 5
        draw.rectangle([sub_name_rect_x, sub_name_rect_y, sub_name_rect_x + sub_rect_w, sub_name_rect_y + sub_name_rect_h], outline="gray", width=2)
        # 이름 텍스트 중앙 정렬
        sub_name_bbox = draw.textbbox((0, 0), sub_name, font=name_font)
        sub_name_text_w = sub_name_bbox[2] - sub_name_bbox[0]
        sub_name_text_h = sub_name_bbox[3] - sub_name_bbox[1]
        sub_name_x = sub_name_rect_x + (sub_rect_w - sub_name_text_w) // 2
        sub_name_y = sub_name_rect_y + (sub_name_rect_h - sub_name_text_h) // 2 - sub_name_bbox[1]
        draw.text((sub_name_x, sub_name_y), sub_name, fill="black", font=name_font)
    return img


async def get_ranklist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where attrib not like :attpatt order by orderNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        rank_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
        return rank_list
    except:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")


async def get_rankdtl(rankno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where rankNo = :rankNo")
        result = await db.execute(query, {"rankNo": rankno})
        rank_dtl = result.fetchone()
        return rank_dtl
    except:
        raise HTTPException(status_code=500, detail="Database query failed(RANKdtl)")


async def get_boarddtl(boardno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsBoard where boardNo = :boardno")
        result = await db.execute(query, {"boardno": boardno})
        boarddtl = result.fetchone()
        return boarddtl
    except:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")


async def get_requests(db: AsyncSession):
    try:
        query = text(
            "SELECT a.*, b.memberName FROM requestMessage a left join lionsMember b on a.memberNo = b.memberNo where a.attrib not like :attxxx")
        result = await db.execute(query, {"attxxx": '%XXX%'})
        requests = result.fetchall()
        return requests
    except:
        raise HTTPException(status_code=500, detail="Database query failed(REQUEST)")


@app.get("/favicon.ico")
async def favicon():
    return {"detail": "Favicon is served at /static/favicon.ico"}


@app.post("/uploaddoc/{clubno}")
async def upload_doc(request: Request, clubno: int, file: UploadFile = File(...),
                     db: AsyncSession = Depends(get_db)):
    try:
        contents = await file.read()
        # 데이터베이스에 저장
        query = text("INSERT INTO lionsDoc (clubNo,cDocument) VALUES (:memno, :docs)")
        result = await db.execute(query, {"memno": clubno, "docs": contents})
        await db.commit()
        return RedirectResponse(f"/doclist/{clubno}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/doclist/{clubno}", status_code=303)


async def resize_image_if_needed(contents: bytes, max_bytes: int = 1048576) -> bytes:
    if len(contents) <= max_bytes:
        return contents
    image = Image.open(io.BytesIO(contents))
    format = image.format if image.format else 'JPEG'
    quality = 85  # JPEG의 경우
    for trial in range(10):
        buffer = io.BytesIO()
        save_kwargs = {'format': format}
        if format.upper() in ['JPEG', 'JPG']:
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        image.save(buffer, **save_kwargs)
        data = buffer.getvalue()
        if len(data) <= max_bytes:
            return data
        if format.upper() in ['JPEG', 'JPG'] and quality > 30:
            quality -= 10
        else:
            w, h = image.size
            image = image.resize((int(w * 0.9), int(h * 0.9)), Image.LANCZOS)
    return data


@app.post("/upload/{memberno}")
async def upload_image(request: Request, memberno: int, file: UploadFile = File(...),
                       db: AsyncSession = Depends(get_db)):
    try:
        # 이미지 파일인지 확인
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        # 파일 읽기
        contents = await file.read()
        # 이미지 사이즈 조절
        contents = await resize_image_if_needed(contents, max_bytes=1048576)
        # 데이터베이스에 이미지 저장
        query = text("INSERT INTO memberPhoto (memberNo, mPhoto) VALUES (:memno, :photo)")
        await db.execute(query, {"memno": memberno, "photo": contents})
        await db.commit()
        # 썸네일 생성 및 저장
        await save_thumbnail(contents, memberno)
        # 리다이렉트
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.post("/uploadnamecard/{memberno}")
async def upload_ncimage(request: Request, memberno: int, file: UploadFile = File(...),
                         db: AsyncSession = Depends(get_db)):
    try:
        # 이미지 파일인지 확인
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        # 파일 읽기
        contents = await file.read()
        # 이미지 사이즈 조절
        contents = await resize_image_if_needed(contents, max_bytes=1048576)
        # 데이터베이스에 이미지 저장
        query = text("INSERT INTO memberNamecard (memberNo, ncardPhoto) VALUES (:memno, :photo)")
        await db.execute(query, {"memno": memberno, "photo": contents})
        await db.commit()
        # 썸네일 생성 및 저장
        await save_ncthumbnail(contents, memberno)
        # 리다이렉트
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.post("/uploadspphoto/{memberno}")
async def upload_spimage(request: Request, memberno: int, file: UploadFile = File(...),
                         db: AsyncSession = Depends(get_db)):
    try:
        # 이미지 파일인지 확인
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File type not supported.")
        # 파일 읽기
        contents = await file.read()
        # 사이즈 조절
        contents = await resize_image_if_needed(contents, max_bytes=1048576)
        # 데이터베이스에 이미지 저장
        query = text("INSERT INTO memberSpouse (memberNo, spousePhoto) VALUES (:memno, :photo)")
        await db.execute(query, {"memno": memberno, "photo": contents})
        await db.commit()
        # 리다이렉트
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


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
        "SELECT userNo, userName,userRole, defaultRegion, defaultClubno FROM lionsUser WHERE userId = :username AND userPassword = password(:password)")
    result = await db.execute(query, {"username": username, "password": password})
    user = result.fetchone()
    if user is None:
        return templates.TemplateResponse("login/login.html", {"request": request, "error": "Invalid credentials"})
    # 서버 세션에 사용자 ID 저장
    request.session["user_No"] = user[0]
    request.session["user_Name"] = user[1]
    request.session["user_Role"] = user[2]
    request.session["user_Region"] = user[3]
    request.session["user_Clubno"] = user[4]
    return RedirectResponse(url="/success", status_code=303)


# 로그인 성공 페이지
@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_Role = request.session.get("user_Role")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "user_Role": user_Role, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/userEdit", response_class=HTMLResponse)
async def user_edit(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login/userEdit.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/userHome", response_class=HTMLResponse)
async def user_home(request: Request):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/mainClub.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/rmemberList/{regno}", response_class=HTMLResponse)
async def rmemberList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    rmember = await get_regionmemberlist(regno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/regionmemberList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "rmember": rmember, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/memberList", response_class=HTMLResponse)
async def memberList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    members = await get_memberlist(db)
    print(members)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/memberList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "members": members, "user_region": user_region, "user_clubno": user_clubno})


@app.api_route("/addmember", response_class=HTMLResponse, methods=["GET", "POST"])
async def addmember(request: Request, db: AsyncSession = Depends(get_db)):
    memberName = "신규추가 회원"
    query = text(f"INSERT into lionsMember (memberName) values (:membername)")
    await db.execute(query, {"membername": memberName})
    await db.commit()
    return RedirectResponse("/memberList", status_code=303)


@app.get("/memberdetail/{memberno}", response_class=HTMLResponse)
async def memberList(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    memberdtl = await get_memberdetail(memberno, db)
    myphoto = await get_photo(memberno, db)
    ncphoto = await get_namecard(memberno, db)
    spphoto = await get_spphoto(memberno, db)
    clublist = await get_clublist(db)
    ranklist = await get_ranklist(db)
    if not user_No:
        return RedirectResponse(url="/")
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "memberdtl": memberdtl, "myphoto": myphoto, "clublist": clublist,
                                       "ranklist": ranklist, "ncphoto": ncphoto, "spphoto": spphoto, "user_region": user_region, "user_clubno": user_clubno})


@app.post("/update_memberdtl/{memberno}", response_class=HTMLResponse)
async def update_memberdtl(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "memberName": form_data.get("membername"),
        "memberMF": form_data.get("gender"),
        "memberBirth": form_data.get("birthdate"),
        "memberSns": form_data.get("memberSns"),
        "memberAddress": form_data.get("home_address"),
        "memberPhone": form_data.get("contact"),
        "memberEmail": form_data.get("email"),
        "memberJoindate": form_data.get("joindate"),
        "clubNo": form_data.get("clublst"),
        "sponserNo": form_data.get("sponserNo"),
        "addMemo": form_data.get("memo"),
        "rankNo": form_data.get("ranklst"),
        "officeAddress": form_data.get("office_address"),
        "spouseName": form_data.get("spname"),
        "spousePhone": form_data.get("spphone"),
        "spouseBirth": form_data.get("spbirth"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE lionsMember SET {set_clause} WHERE memberNo = :memberNo")
    update_fields["memberNo"] = memberno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/memberdetail/{memberno}", status_code=303)


@app.get("/clubmemberList/{clubno}/{clubname}", response_class=HTMLResponse)
async def memberList(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    cmembers = await get_clubmemberlist(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubName": clubname, "cmembers": cmembers, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/clubmemberCards/{clubno}/{clubname}", response_class=HTMLResponse)
async def memberList(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    memberList = await get_clubmembercard(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/memberCards.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubName": clubname, "memberList": memberList, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/clubList", response_class=HTMLResponse)
async def clubList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM lionsClub where attrib not like '%XXXUP%'")
    result = await db.execute(query)
    club_list = result.fetchall()  # 클럽 데이터를 모두 가져오기
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "club_list": club_list, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/editclub/{clubno}", response_class=HTMLResponse)
async def editclub(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM lionsClub where clubNo = :clubNo")
    result = await db.execute(query, {"clubNo": clubno})
    clubdtl = result.fetchone()
    clubdocs = await get_clubdocs(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubdtl": clubdtl, "clubdocs": clubdocs, "user_clubno": clubno, "user_region": user_region})


@app.get("/editclubdoc/{clubno}", response_class=HTMLResponse)
async def editclubdoc(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM lionsClub where clubNo = :clubNo")
    result = await db.execute(query, {"clubNo": clubno})
    clubdtl = result.fetchone()
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubDocs.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubdtl": clubdtl, "user_region": user_region, "user_clubno": user_clubno})


@app.post("/updateclubdoc/{clubno}")
async def updateclubdoc(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4docs = {
        "clubNo": clubno,
        "docType": form_data.get("doctype"),
        "docTitle": form_data.get("title"),
        "cDocument": form_data.get("content"),
    }
    querys = text(f"SELECT * from lionsDoc where clubNo = :clubNo and docType = :docType")
    result = await db.execute(querys, data4docs)
    docresult = result.fetchone()
    if docresult:
        queryup = text(
            f"UPDATE lionsDoc SET modDate = :timenow , attrib = :updattrib WHERE clubNo = :clubno and docType = :doctype")
        timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.execute(queryup, {"timenow": timenow, "updattrib": "XXXUPXXXUP", "clubno": clubno,
                                   "doctype": form_data.get("doctype")})
    query = text(
        f"INSERT INTO lionsDoc (clubNo,docType,docTitle,cDocument) values (:clubNo,:docType,:docTitle,:cDocument)")
    await db.execute(query, data4docs)
    await db.commit()
    return RedirectResponse(f"/editclub/{clubno}", status_code=303)


@app.get("/popup_doc/{docno}")
async def get_popup_content(docno: int, db: AsyncSession = Depends(get_db)):
    cdoc = await get_clubdoc(docno, db)
    print(cdoc)
    if cdoc:
        return HTMLResponse(cdoc)


@app.get("/listnotice/{regionno}", response_class=HTMLResponse)
async def editnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM boardMessage where regionNo = :regionNo and attrib not like '%XXXUP%'")
    result = await db.execute(query, {"regionNo": regionno})
    noticelist = result.fetchall()
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/noticeList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "notices": noticelist, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/addnotice/{regionno}", response_class=HTMLResponse)
async def addnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    now = datetime.now()
    two_weeks = now + timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    from_date = now.strftime(fmt)
    to_date = two_weeks.strftime(fmt)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/addnotice.html",{"request": request, "user_No": user_No, "user_Name": user_Name,"user_region": user_region, "user_clubno": user_clubno, "from_date": from_date, "to_date": to_date})


@app.get("/editnotice/{messageno}", response_class=HTMLResponse)
async def editnotice(request:Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM boardMessage where messageNo = :messageno")
    result = await db.execute(query, {"messageno": messageno})
    notice = result.fetchone()
    now = datetime.now()
    two_weeks = now + timedelta(days=14)
    fmt = '%Y-%m-%dT00:00'
    from_date = notice[6] if notice[6] is not None else now.strftime(fmt)
    to_date = notice[7] if notice[7] is not None else two_weeks.strftime(fmt)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/editnotice.html",{"request": request, "user_No": user_No, "user_Name": user_Name,"user_region": user_region, "user_clubno": user_clubno, "notice": notice, "from_date": from_date, "to_date": to_date})


@app.post("/updatenotice/{messageno}", response_class=HTMLResponse)
async def update_clubdtl(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    form_data = await request.form()
    data4update = {
        "messageTitle": form_data.get("nottitle"),
        "MessageConts": form_data.get("notmessage"),
        "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE boardMessage SET {set_clause} WHERE messageNo = :messageNo")
    update_fields["messageNo"] = messageno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/listnotice/{user_region}", status_code=303)


@app.post("/removenotice/{messageno}", response_class=HTMLResponse)
async def remove(request: Request, messageno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text(f"UPDATE boardMessage SET attrib = :XXUP WHERE messageNo = :messageNo")
    await db.execute(query, {"XXUP":"XXXUPXXXUP", "messageNo": messageno})
    await db.commit()
    return RedirectResponse(f"/listnotice/{user_region}", status_code=303)


@app.post("/insertnotice/{regionno}", response_class=HTMLResponse)
async def insertnotice(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    form_data = await request.form()
    data4insert = {
        "regionNo": regionno,
        "messageTitle": form_data.get("nottitle"),
        "MessageConts": form_data.get("notmessage"),
        "noticeFrom": form_data.get("notfrom"),
        "noticeTo": form_data.get("notto"),
    }
    insert_fields = {key: value for key, value in data4insert.items() if value is not None}
    columns = ", ".join(insert_fields.keys())
    values = ", ".join([f":{key}" for key in insert_fields.keys()])
    query = text(f"INSERT INTO boardMessage ({columns}) VALUES ({values})")
    await db.execute(query, insert_fields)
    await db.commit()
    return RedirectResponse(f"/listnotice/{user_region}", status_code=303)


@app.post("/updateclub/{clubno}", response_class=HTMLResponse)
async def update_clubdtl(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "clubName": form_data.get("clubname"),
        "estDate": form_data.get("estdate"),
        "regionNo": form_data.get("regno"),
        "officeAddr": form_data.get("offaddr"),
        "officeTel": form_data.get("offtel"),
        "officeFax": form_data.get("offfax"),
        "officeEmail": form_data.get("offemail"),
        "officeWeb": form_data.get("offweb"),
        "modDate": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    update_fields = {key: value for key, value in data4update.items() if value is not None}
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    query = text(f"UPDATE lionsClub SET {set_clause} WHERE clubNo = :clubNo")
    update_fields["clubNo"] = clubno
    await db.execute(query, update_fields)
    await db.commit()
    return RedirectResponse(f"/editclub/{clubno}", status_code=303)


@app.get("/regionclubList/{regno}", response_class=HTMLResponse)
async def regionclubList(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    club_list = await get_regionclublist(regno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("member/regionclubList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "club_list": club_list, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/rankList", response_class=HTMLResponse)
async def rankList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    rank_list = await get_ranklist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/rankList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "rank_list": rank_list, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/rankDetail/{rankno}", response_class=HTMLResponse)
async def rankDtl(request: Request, rankno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    rank_dtl = await get_rankdtl(rankno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/rankDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "rank_dtl": rank_dtl, "user_region": user_region, "user_clubno": user_clubno})


@app.post("/update_rank/{rankno}", response_class=HTMLResponse)
async def update_rankdtl(request: Request, rankno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "rankNo": rankno,
        "rankTitlekor": form_data.get("rankkor"),
        "rankTitleeng": form_data.get("rankeng"),
        "rankDiv": form_data.get("ranktype"),
        "orderNo": form_data.get("orderno"),
        "useYN": form_data.get("useyn"),
    }
    mdatenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    query = text(
        f"UPDATE lionsRank SET rankTitlekor = :rankTitlekor, rankTitleeng = :rankTitleeng, rankDiv = :rankDiv, orderNo = :orderNo, useYN = :useYN WHERE rankNo = :rankNo")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/rankDetail/{rankno}", status_code=303)


@app.get("/add_rank", response_class=HTMLResponse)
async def add_rank(request: Request, db: AsyncSession = Depends(get_db)):
    query = text(
        f"INSERT INTO lionsRank (rankTitlekor, rankTitleeng, rankDiv, orderNo) values (:rankTitlekor, :rankTitleeng, :rankDiv, :orderNo)")
    await db.execute(query,
                     {"rankTitlekor": "새로 등록된 직책", "rankTitleeng": "New Rank", "rankDiv": "CLUB", "orderNo": "0"})
    await db.commit()
    return RedirectResponse(f"/rankList", status_code=303)


@app.get("/clubStaff/{clubno}/{clubName}", response_class=HTMLResponse)
async def clubstaff(request: Request, clubno: int, clubName: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    staff_dtl = await get_clubstaff(clubno, db)
    clubmember = await get_clubmemberlist(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/clubStaff.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubName": clubName, "clubno": clubno,
                                       "staff_dtl": staff_dtl, "clubmember": clubmember, "user_region": user_region, "user_clubno": user_clubno})


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


@app.get("/regionList", response_class=HTMLResponse)
async def dictList(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    region_list = await get_regionlist(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/regionList.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "region_list": region_list, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/editregion/{regno}", response_class=HTMLResponse)
async def editclub(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM lionsRegion where regionNo = :regNo and attrib not like :atts")
    result = await db.execute(query, {"regNo": regno, "atts": "%XXX%"})
    regiondtl = result.fetchone()
    rankmembers = await get_rankmemberlist(15, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin/regionDetail.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "regiondtl": regiondtl, "rankmembers": rankmembers, "user_region": user_region, "user_clubno": user_clubno})


@app.get("/editbis/{memberno}", response_class=HTMLResponse)
async def editbis(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    query = text("SELECT * FROM memberBusiness where memberNo = :memberno and attrib not like :atts")
    result = await db.execute(query, {"memberno": memberno, "atts": "%XXX%"})
    bisdtl = result.fetchone()
    return templates.TemplateResponse("business/regBis.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "memberno": memberno, "user_region": user_region, "user_clubno": user_clubno,
                                       "bisdtl": bisdtl})


@app.post("/update_business/{memberno}", response_class=HTMLResponse)
async def update_bisdtl(request: Request, memberno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "dt1": memberno,
        "dt2": form_data.get("bistitle"),
        "dt3": form_data.get("bisrank"),
        "dt4": form_data.get("bistype"),
        "dt5": form_data.get("bistypedtl"),
        "dt6": form_data.get("offtel"),
        "dt7": form_data.get("offaddress"),
        "dt8": form_data.get("offemail"),
        "dt9": form_data.get("offpost"),
        "dt10": form_data.get("offweb"),
        "dt11": form_data.get("offsns"),
        "dt12": form_data.get("offemo")
    }
    queryup = text(f"UPDATE memberBusiness SET attrib = :attr WHERE memberNo = :memberno")
    await db.execute(queryup, {"memberno": memberno, "attr": "XXXUPXXXUP"})
    query = text(
        f"INSERT INTO memberBusiness (memberNo,bisTitle, bisRank, bisType,bistypeTitle,officeTel,officeAddress,officeEmail,officePostNo,officeWeb,officeSns,bisMemo) values (:dt1,:dt2,:dt3,:dt4,:dt5,:dt6,:dt7,:dt8,:dt9,:dt10,:dt11,:dt12)")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/editbis/{memberno}", status_code=303)


@app.post("/updateregion/{regno}", response_class=HTMLResponse)
async def update_regdtl(request: Request, regno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    data4update = {
        "regionNo": form_data.get("regno"),
        "chairmanNo": form_data.get("chairmno"),
        "regionSlog": form_data.get("slog"),
        "yearFrom": form_data.get("yearfrom"),
        "yearTo": form_data.get("yearto"),
    }
    mdatenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    queryup = text(f"UPDATE lionsRegion SET attrib = :attr, modDate = :mdate WHERE regionNo = :regno")
    await db.execute(queryup, {"regno": regno, "attr": "XXXUPXXXUP", "mdate": mdatenow})
    query = text(
        f"INSERT INTO lionsRegion (regionNo,chairmanNo,regionSlog,yearFrom,yearTo) values (:regionNo,:chairmanNo,:regionSlog, :yearFrom, :yearTo)")
    await db.execute(query, data4update)
    await db.commit()
    return RedirectResponse(f"/editregion/{regno}", status_code=303)


@app.get("/boardManager/{regionno}", response_class=HTMLResponse)
async def boardManager(request: Request, regionno: int, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    clublist = await get_regionboardlist(regionno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/boardMain.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clublist": clublist, "user_Region": user_region, "user_Clubno": user_clubno})


@app.get("/boardList/{clubno}/{clubname}", response_class=HTMLResponse)
async def clubboardlist(request: Request, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    clubboards = await get_clubboards(clubno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/clubboardlist.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "clubboards": clubboards, "clubname": clubname, "user_clubno": clubno, "user_region": user_region})


@app.get("/editboard/{boardno}/{clubname}", response_class=HTMLResponse)
async def editboard(request: Request, boardno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    boarddtl = await get_boarddtl(boardno, db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/editboard.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "boarddtl": boarddtl, "clubname": clubname, "user_region": user_region, "user_clubno": user_clubno })


@app.api_route("/addboard/{clubno}", response_class=HTMLResponse, methods=["GET", "POST"])
async def addboard(request: Request, clubno: int, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    btitle = form_data.get("btitle")
    if not btitle:
        btitle = "새로 만든 게시판(제목 변경 필요)"
    btype = form_data.get("btype")
    if not btype:
        btype = "BOARD"
    query = text(f"INSERT into lionsBoard (clubNo, boardTitle, boardType) values (:clubNo, :boardTitle, :boardType)")
    await db.execute(query, {"clubNo": clubno, "boardTitle": btitle, "boardType": btype})
    await db.commit()
    return RedirectResponse(f"/boardList/{clubno}", status_code=303)


@app.get("/requestList", response_class=HTMLResponse)
async def requestlist(request: Request, db: AsyncSession = Depends(get_db)):
    user_No = request.session.get("user_No")
    user_Name = request.session.get("user_Name")
    user_region = request.session.get("user_Region")
    user_clubno = request.session.get("user_Clubno")
    requests = await get_requests(db)
    if not user_No:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("board/requestlist.html",
                                      {"request": request, "user_No": user_No, "user_Name": user_Name,
                                       "requests": requests, "user_region": user_region, "user_clubno": user_clubno})


@app.post("/updaterequest/{requestno}", response_class=HTMLResponse)
async def updaterequest(request: Request, requestno: int, db: AsyncSession = Depends(get_db)):
    query = text(f"UPDATE requestMessage SET attrib = :attr WHERE requestNo = :requestno")
    await db.execute(query, {"requestno": requestno, "attr": "XXXUPXXXUP"})
    await db.commit()
    return JSONResponse({"result": "ok"})


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
    img = make_slogan_image(slogan, memberno, name, width=400, height=400, sub_members=sub_members)
    save_dir = "./static/img/members"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{clubno}logo.png")
    img.save(save_path, format="PNG")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.api_route("/updateboard/{boardno}/{clubno}/{clubname}", response_class=HTMLResponse, methods=["GET", "POST"])
async def addboard(request: Request, boardno: int, clubno: int, clubname: str, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    btitle = form_data.get("btitle")
    btype = form_data.get("btype")
    query = text(f"update lionsBoard set boardTitle=:boardTitle,boardType=:boardType where boardNo=:boardNo")
    await db.execute(query, {"boardNo": boardno, "boardTitle": btitle, "boardType": btype})
    await db.commit()
    return RedirectResponse(f"/boardList/{clubno}/{clubname}", status_code=303)


# 로그아웃 처리
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()  # 세션 삭제
    return RedirectResponse(url="/")


@app.get("/phapp/clubList/{regionno}")
async def phappclublist(regionno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT clubNo, clubName, regionNo FROM lionsClub where regionNo = :regionNo ")
        result = await db.execute(query, {"regionNo": regionno})
        rows = result.fetchall()
        result = [{"clubNo": row[0], "clubName": row[1], "regionNo": row[2]} for row in rows]
    except:
        print("error")
    finally:
        return {"clubs": result}


@app.get("/phapp/memberList/{clubno}")
async def phappmemberlist(clubno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo where lm.clubNo = :clubno order by lm.memberJoindate")
        result = await db.execute(query, {"clubno": clubno})
        rows = result.fetchall()
        result = [{"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3]} for row in
                  rows]
    except:
        print("error")
    finally:
        return {"members": result}


@app.get("/phapp/clubdocs/{clubno}")
async def clubdocs(clubno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT * from lionsDoc where clubNo = :clubno and attrib not like :attrib")
        result = await db.execute(query, {"clubno": clubno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result = [{"docNo": row[0], "docType": row[2], "docTitle": row[3]} for row in rows]
    except:
        print("error")
    finally:
        return {"docs": result}


@app.get("/phapp/docviewer/{docno}")
async def docviewer(docno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT cDocument, docTitle from lionsDoc where docNo = :docno ")
        result = await db.execute(query, {"docno": docno})
        row = result.fetchone()
        result = [{"cDoc": row[0], "title": row[1]}]
    except:
        print("error")
    finally:
        return {"doc": result}


@app.get("/phapp/notice/{regionno}")
async def notice(regionno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT * from boardMessage where regionNo = :regionno and attrib not like :attrib")
        result = await db.execute(query, {"regionno": regionno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result = [{"noticeNo": row[0], "writer": row[3], "noticeTitle": row[4]} for row in rows]
    except:
        print("error")
    finally:
        return {"docs": result}


@app.get("/phapp/noticeViewer/{messageno}")
async def notice(messageno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT * from boardMessage where messageNo = :messageno and attrib not like :attrib")
        result = await db.execute(query, {"messageno": messageno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result = [{"noticeNo": row[0], "writer": row[3], "noticeTitle": row[4], "noticeCont": row[5]} for row in rows]
    except:
        print("error")
    finally:
        return {"docs": result}


@app.get("/phapp/rmemberList/")
async def phapprmemberlist(db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName FROM lionsMember lm "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join lionsClub lc on lm.clubNo = lc.clubNo "
            "where lm.rankNo != :rankno order by lm.memberJoindate ")
        result = await db.execute(query, {"rankno": 19})  # 회원 제외
        rows = result.fetchall()
        result = [
            {"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3], "clubName": row[4]}
            for row in
            rows]
    except:
        print("error")
    finally:
        return {"members": result}


@app.get("/phapp/rnkmemberList/{regionno}")
async def phapprnkmemberlist(regionno:int,db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName FROM lionsMember lm "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join lionsClub lc on lm.clubNo = lc.clubNo "
            "where lm.rankNo != :rankno and lc.regionNo = :regionno order by lc.clubNo, lr.orderNo, lm.memberJoindate ")
        result = await db.execute(query, {"rankno": 19, "regionno": regionno})  # 회원 제외
        rows = result.fetchall()
        result = [
            {"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3], "clubName": row[4]}
            for row in
            rows]
    except:
        print("error")
    finally:
        return {"members": result}


@app.get("/phapp/searchmember/{keywd}")
async def searchmember(keywd: str, db: AsyncSession = Depends(get_db)):
    try:
        keywd = f"%{keywd}%"
        print(keywd)
        query = text(
            "SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName FROM lionsMember lm "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join lionsClub lc on lm.clubNo = lc.clubNo "
            "left join memberBusiness mb on lm.memberNo = mb.memberNo "
            "where lm.memberName like :keyword or lm.memberPhone like :keyword or lm.memberAddress like :keyword "
            "or lm.memberEmail like :keyword or lm.addMemo like :keyword or lm.officeAddress like :keyword "
            "or mb.bisTitle like :keyword or mb.bisType like :keyword or mb.bistypeTitle like :keyword or mb.bisMemo like :keyword order by lm.memberJoindate")
        result = await db.execute(query, {"keyword": keywd})  # 키워드 검색
        rows = result.fetchall()
        result = [
            {"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3], "clubName": row[4]}
            for row in rows]
        print(result)
    except:
        print("error")
    finally:
        return {"members": result}


@app.get("/phapp/rsearchmember/{regionno}/{keywd}")
async def rsearchmember(regionno:int, keywd: str, db: AsyncSession = Depends(get_db)):
    try:
        keywd = f"%{keywd}%"
        query = text(
            "SELECT DISTINCT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName FROM lionsMember lm "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join lionsClub lc on lm.clubNo = lc.clubNo "
            "left join memberBusiness mb on lm.memberNo = mb.memberNo "
            "where lc.regionNo = :regionno AND (lm.memberName like :keyword or lm.memberPhone like :keyword or lm.memberAddress like :keyword "
            "or lm.memberEmail like :keyword or lm.addMemo like :keyword or lm.officeAddress like :keyword "
            "or mb.bisTitle like :keyword or mb.bisType like :keyword or mb.bistypeTitle like :keyword or mb.bisMemo like :keyword) order by lm.memberJoindate")
        result = await db.execute(query, {"keyword": keywd, "regionno":regionno})  # 키워드 검색
        rows = result.fetchall()
        result = [
            {"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3], "clubName": row[4]}
            for row in rows]
    except:
        print("error")
    finally:
        return {"members": result}


@app.get("/phapp/memberDtl/{memberno}")
async def phappmemberlist(memberno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "WITH LatestPhoto AS (SELECT mPhoto, memberNo,ROW_NUMBER() OVER (PARTITION BY memberNo ORDER BY regDate DESC) AS rn FROM memberPhoto ),"
            "LatestNC AS ( SELECT ncardPhoto, memberNo,ROW_NUMBER() OVER (PARTITION BY memberNo ORDER BY regDate DESC) AS rn FROM memberNamecard ),"
            "LatestSP AS ( SELECT spousePhoto, memberNo,ROW_NUMBER() OVER (PARTITION BY memberNo ORDER BY regDate DESC) AS rn FROM memberSpouse )"
            "SELECT lm.*, (TO_BASE64(lp.mPhoto)), lr.rankTitlekor, lc.clubName, (TO_BASE64(ln.ncardPhoto)), (TO_BASE64(ls.spousePhoto)), mb.* FROM lionsMember lm "
            "left join latestPhoto lp on lm.memberNo = lp.memberNo and lp.rn = 1 "
            "left join latestNC ln on lm.memberNo = ln.memberNo and ln.rn = 1 "
            "left join latestSP ls on ls.memberNo = ln.memberNo and ls.rn = 1 "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join lionsClub lc on lm.clubNo = lc.clubNo "
            "left join memberBusiness mb on lm.memberNo = mb.memberNo "
            "where lm.memberNo = :memberno")
        result = await db.execute(query, {"memberno": memberno})
        rows = result.fetchone()
        if rows[17]=='N':
            result = [{"memberNo": rows[0], "memberName": rows[1], "memberPhone": rows[6], "mPhotoBase64": rows[18],
                   "clubNo": rows[9],
                   "rankTitle": rows[19], "memberMF": rows[2], "memberAddress": rows[5], "memberEmail": rows[7],
                   "memberJoindate": rows[8],
                   "addMemo": rows[11], "memberBirth": rows[3], "clubName": rows[20], "nameCard": rows[21],
                   "officeAddress": rows[13],
                   "spouseName": rows[14], "spousePhone": rows[15], "spouseBirth": rows[16], "spousePhoto": rows[22],
                   "bisTitle": rows[25], "bisRank": rows[26], "bisType": rows[27], "bistypeTitle": rows[28],
                   "offtel": rows[29],
                   "offAddress": rows[30], "offEmail": rows[31], "offPost": rows[32], "offWeb": rows[33],
                   "offSns": rows[34], "bisMemo": rows[35]}]
        else:
            result = [{"memberNo": rows[0], "memberName": rows[1], "memberPhone": rows[6], "mPhotoBase64": rows[18],
                       "clubNo": rows[9],
                       "rankTitle": rows[19], "memberMF": rows[2], "memberAddress": "비공개", "memberEmail": "비공개",
                       "memberJoindate": rows[8],
                       "addMemo": rows[11], "memberBirth": "비공개", "clubName": rows[20], "nameCard": "",
                       "officeAddress": "비공개",
                       "spouseName": "비공개", "spousePhone": "비공개", "spouseBirth": "비공개",
                       "spousePhoto": "",
                       "bisTitle": "비공개", "bisRank": "비공개", "bisType": "비공개", "bistypeTitle": "비공개",
                       "offtel": "비공개",
                       "offAddress": "비공개", "offEmail": "비공개", "offPost": "비공개", "offWeb": "비공개",
                       "offSns": "비공개", "bisMemo": "비공개"}]
    except:
        print("Member Detail Phone error")
    finally:
        return {"memberdtl": result}


@app.get("/phapp/mlogin/{phoneno}")
async def mlogin(phoneno: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT clubNo, memberNo from lionsMember where memberSeccode = :phoneno ")
        result = await db.execute(query, {"phoneno": phoneno})
        rows = result.fetchone()
        if rows is None:
            return {"error": "No data found for the given phone number."}
        result = {"clubno": rows[0], "memberno": rows[1]}
        print(result)
    except:
        print("mLogin error")
    finally:
        return result


@app.get("/phapp/rlogin/{regionno}/{phoneno}")
async def mlogin(regionno:int, phoneno: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT lm.clubNo, lm.memberNo, lc.regionNo from lionsMember lm left join lionsClub lc on lc.clubNo = lm.clubNo where lm.memberSeccode = :phoneno and lc.regionNo = :regionno")
        result = await db.execute(query, {"phoneno": phoneno, "regionno": regionno})
        rows = result.fetchone()
        if rows is None:
            return {"error": "No data found for the given phone number."}
        result = {"clubno": rows[0], "memberno": rows[1], "regionno": rows[2]}
        print(result)
    except:
        print("mLogin error")
    finally:
        return result


@app.get("/phapp/zlogin/{phoneno}")
async def mlogin(phoneno: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT lm.clubNo, lm.memberNo, lc.regionNo from lionsMember lm left join lionsClub lc on lc.clubNo = lm.clubNo where lm.memberSeccode = :phoneno")
        result = await db.execute(query, {"phoneno": phoneno})
        rows = result.fetchone()
        if rows is None:
            return {"error": "No data found for the given phone number."}
        result = {"clubno": rows[0], "memberno": rows[1], "regionno": rows[2]}
        print(result)
    except:
        print("mLogin error")
    finally:
        return result


class RequestMessage(BaseModel):
    memberNo: str
    message: str


@app.post("/phapp/requestmessage")
async def request_message(req: RequestMessage, db: AsyncSession = Depends(get_db)):
    try:
        query = text("INSERT INTO requestMessage (memberNo, message) VALUES (:memberNo, :message)")
        await db.execute(query, {"memberNo": req.memberNo, "message": req.message})
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("request_message error:", e)
        raise HTTPException(status_code=500, detail="DB 저장 중 오류 발생")


@app.post("/phapp/maskYN/{memberno}/{msk}")
async def mskyn(memberno:int,msk:str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("UPDATE lionsMember set maskYN = :msk where memberNo = :memberNo")
        await db.execute(query, {"memberNo": memberno , "msk": msk})
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("request_message error:", e)
        raise HTTPException(status_code=500, detail="DB 저장 중 오류 발생")


@app.get("/phapp/getmask/{memberno}")
async def mskyn(memberno:int,db: AsyncSession = Depends(get_db)):
    try:
        query = text("select maskYN from lionsMember where memberNo = :memberNo")
        result = await db.execute(query, {"memberNo": memberno })
        rows = result.fetchone()
        return {"maskYN": rows[0]}
    except Exception as e:
        print("request_message error:", e)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy/privacy.htm", {"request": request})


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

