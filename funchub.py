import os
from PIL import Image, ImageDraw, ImageFont
import os
import io
import base64
import datetime
import asyncio
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from firebase_admin import messaging
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
import jwt
import dotenv

dotenv.load_dotenv()

# 상수 설정
THUMBNAIL_DIR = "./static/img/members"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "my_super_secret_mobile_key_1234!")
ALGORITHM = "HS256"

# Bcrypt 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or not isinstance(hashed_password, str):
        return False
    hashed_password = hashed_password.strip()
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError, TypeError):
        return False

# 토큰 생성 함수
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# FCM 발송 함수
async def send_fcm_topic_notice(clubno: int, title: str, body: str):
    topic = f"club_{clubno}"
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"clubNo": str(clubno)},
        topic=topic,
    )
    response = await asyncio.to_thread(messaging.send, message)
    return response

async def send_fcm_topic_notice_member(memberno: int, title: str, body: str):
    topic = f"member_{memberno}"
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"memberNo": str(memberno)},
        topic=topic,
    )
    response = await asyncio.to_thread(messaging.send, message)
    return response

async def send_fcm_topic_notice_region(regionno: int, title: str, body: str):
    topic = f"region_{regionno}"
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"regionNo": str(regionno)},
        topic=topic,
    )
    response = await asyncio.to_thread(messaging.send, message)
    return response

# 이미지 처리 함수
async def save_thumbnail(image_data: bytes, memberno: int, size=(100, 100)):
    def process():
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail(size)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{memberno}.png")
        image.save(thumbnail_path, format="PNG")
        return thumbnail_path
    return await asyncio.to_thread(process)

async def save_ncthumbnail(image_data: bytes, memberno: int, size=(80, 100)):
    def process():
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail(size)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"nc{memberno}.png")
        image.save(thumbnail_path, format="PNG")
        return thumbnail_path
    return await asyncio.to_thread(process)

async def save_circlelogo(image_data: bytes, circleno: int, size=(200, 200)):
    def process():
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail(size)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{circleno}circlelogo.png")
        image.save(thumbnail_path, format="PNG")
        return thumbnail_path
    return await asyncio.to_thread(process)

async def resize_image_if_needed(contents: bytes, max_bytes: int = 102400) -> bytes:
    if len(contents) <= max_bytes:
        return contents
    def process():
        image = Image.open(io.BytesIO(contents))
        format = image.format if image.format else 'JPEG'
        quality = 85
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
    return await asyncio.to_thread(process)

def get_default_image_base64(mime_type: str = "image/png") -> str:
    default_image_path = "static/img/defaultphoto.png"
    try:
        with open(default_image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_image}"
    except FileNotFoundError:
        raise Exception("Default image file not found.")

def split_text_to_multiline(draw, text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        test_bbox = draw.textbbox((0, 0), test_line, font=font)
        test_width = test_bbox[2] - test_bbox[0]
        if test_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    if len(lines) > 2:
        lines = [lines[0], ' '.join(lines[1:])]
    return '\n'.join(lines)


from PIL import Image, ImageDraw, ImageFont


def make_slogan_image(slogan: str, member_no: int, name: str, width=400, height=520, font_size=22,
                      sub_members=[(2, "서브1"), (3, "서브2")]) -> Image.Image:
    # 🎨 라이온스클럽 상징 컬러
    LIONS_BLUE = "#00338D"
    LIONS_GOLD = "#F2A900"
    BG_COLOR = "#F4F6F9"

    img = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 📝 폰트 설정 (윈도우 맑은고딕 추가)
    font_paths = [
        "malgunbd.ttf",  # 윈도우 맑은 고딕 볼드
        "malgun.ttf",  # 윈도우 맑은 고딕
        "NanumGothicBold.ttf",
        "NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "AppleGothic.ttf"
    ]

    font = None
    name_font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            name_font = ImageFont.truetype(path, 16)
            break
        except IOError:
            continue

    if font is None:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # 1. 상단 헤더 영역
    header_height = 110
    draw.rectangle([0, 0, width, header_height], fill=LIONS_BLUE)

    max_slogan_width = int(width * 0.85)
    # (기존에 가지고 계신 split_text_to_multiline 함수 사용 가정)
    multiline_slogan = split_text_to_multiline(draw, slogan, font, max_slogan_width)

    bbox = draw.multiline_textbbox((0, 0), multiline_slogan, font=font, spacing=6)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (width - text_width) // 2
    y = (header_height - text_height) // 2 - bbox[1]

    draw.multiline_text((x + 2, y + 2), multiline_slogan, fill="#001540", font=font, spacing=6, align="center")
    draw.multiline_text((x, y), multiline_slogan, fill=LIONS_GOLD, font=font, spacing=6, align="center")

    # 프로필 그리기 헬퍼 함수 (수정됨)
    def draw_member_card(m_no, m_name, cx, cy, img_w, img_h):
        border_w = 4
        tag_h = 32
        radius = 15  # 모서리 라운드 값
        shadow_offset = 5  # 그림자 위치 오프셋
        gap = 12  # 사진과 이름표 사이의 간격

        # 사진 테두리 영역 계산
        left = cx - img_w // 2 - border_w
        top = cy - border_w
        right = cx + img_w // 2 + border_w
        bottom = cy + img_h + border_w

        # 1. 그림자 효과 (사진 영역 뒤에 약간 어긋나게 배치)
        shadow_color = "#D4D8E2"  # 배경색보다 약간 어두운 그림자 색상
        draw.rounded_rectangle(
            [left + shadow_offset, top + shadow_offset, right + shadow_offset, bottom + shadow_offset],
            radius=radius, fill=shadow_color
        )

        # 2. 골드 테두리 (라운드 처리)
        draw.rounded_rectangle([left, top, right, bottom], radius=radius, fill=LIONS_GOLD)

        # 3. 프로필 이미지 로드 및 마스킹
        photo_x = cx - img_w // 2
        photo_y = cy

        profile_img = None
        # mphoto_{m_no}.jpg 또는 png 확인
        for ext in ["jpg", "png"]:
            try:
                profile_img = Image.open(f"./static/img/members/mphoto_{m_no}.{ext}").convert("RGBA")
                break
            except Exception:
                continue

        if profile_img:
            profile_img = profile_img.resize((img_w, img_h))
        else:
            # 이미지가 없을 경우 회색 배경 대체
            profile_img = Image.new("RGBA", (img_w, img_h), "#E0E0E0")

        # 이미지를 둥글게 자르기 위한 마스크 생성
        img_mask = Image.new("L", (img_w, img_h), 0)
        mask_draw = ImageDraw.Draw(img_mask)
        # 테두리 두께만큼 안쪽으로 들어간 라운드 값 적용
        mask_draw.rounded_rectangle((0, 0, img_w, img_h), radius=max(1, radius - border_w), fill=255)

        # 마스크를 적용하여 이미지 합성
        img.paste(profile_img, (photo_x, photo_y), img_mask)

        # 4. 네임택 (사진과 분리됨)
        tag_y = bottom + gap
        tag_left = cx - img_w // 2 - border_w
        tag_right = cx + img_w // 2 + border_w

        # 네임택도 통일감을 위해 약간 둥글게 처리
        draw.rounded_rectangle([tag_left, tag_y, tag_right, tag_y + tag_h], radius=6, fill=LIONS_BLUE)

        n_bbox = draw.textbbox((0, 0), m_name, font=name_font)
        n_w = n_bbox[2] - n_bbox[0]
        n_h = n_bbox[3] - n_bbox[1]
        nx = cx - n_w // 2
        ny = tag_y + (tag_h - n_h) // 2 - n_bbox[1]
        draw.text((nx, ny), m_name, fill="white", font=name_font)

    # 2. 메인 멤버
    main_y = header_height + 25
    main_img_h = 140
    main_tag_h = 32
    border_width = 4
    gap_between = 12
    draw_member_card(member_no, name, width // 2, main_y, 110, main_img_h)

    # 3. 서브 멤버
    if sub_members:
        # 사진과 네임택이 분리되면서 전체 높이가 늘어났으므로 서브 멤버의 Y좌표도 조정
        sub_y = main_y + main_img_h + (border_width * 2) + gap_between + main_tag_h + 25
        gap_w = width // (len(sub_members) + 1)

        for i, (sub_no, sub_name) in enumerate(sub_members):
            cx = gap_w * (i + 1)
            draw_member_card(sub_no, sub_name, cx, sub_y, 90, 115)

    return img


def row_to_dict(row):
    d = dict(row._mapping)
    for k, v in d.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            d[k] = v.isoformat()
    return d

# 데이터베이스 조회 함수들
async def get_clublist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClub where attrib not like :attpatt")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBLIST)")

async def get_circlelist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsCircle where circleType not in (:vtoc) and attrib not like :attpatt")
        result = await db.execute(query, {"attpatt": "%XXX%", "vtoc": 'VOTEC'})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CIRCLELIST)")

async def get_clubboards(clubno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsBoard where attrib not like :attpatt AND clubno = :clubno")
        result = await db.execute(query, {"attpatt": "%XXX%", "clubno": clubno})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBBOARDS)")


async def get_photo(memberno: int, db: AsyncSession):
    path = f"./static/img/members/mphoto_{memberno}.png"
    if os.path.exists(path):
        return f"/static/img/members/mphoto_{memberno}.png"
    return None

async def get_namecard(memberno: int, db: AsyncSession):
    path = f"./static/img/members/ncard_{memberno}.png"
    if os.path.exists(path):
        return f"/static/img/members/ncard_{memberno}.png"
    return None

async def get_spphoto(memberno: int, db: AsyncSession):
    path = f"./static/img/members/sphoto_{memberno}.png"
    if os.path.exists(path):
        return f"/static/img/members/sphoto_{memberno}.png"
    return None


async def get_regionclublist(region: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClub where attrib not like :attpatt and regionNo = :regno")
        result = await db.execute(query, {"attpatt": "%XXX%", "regno": region})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")

async def get_regionboardlist(region: int, db: AsyncSession):
    try:
        query = text(
            "select lc.clubName , lb.clubNo, GROUP_CONCAT(lb.boardTitle SEPARATOR ',') AS boardDetails, count(lb.boardNo ) from lionsBoard lb "
            "left join lionsClub lc on lb.clubNo = lc.clubNo and lc.regionNo = :regno  group by lb.clubNo order by lb.clubNo")
        result = await db.execute(query, {"regno": region})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")

async def get_regionmemberlist(region: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lcc.clubName, lr.rankTitlekor FROM lionsMember lm left join lionsClub lcc on lm.clubNo = lcc.clubNo "
            "left join lionsRank lr on lm.rankNo = lr.rankNo where lm.clubNo in (select lc.clubno from lionsClub lc where lc.regionNo = :regno) order by lm.clubNo, lm.memberJoindate")
        result = await db.execute(query, {"regno": region})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")

async def get_circlememberlist(circleno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lcc.clubName, lr.rankTitlekor, lr2.rankTitlekor as circleRanktitle FROM lionsMember lm "
            "left join lionsClub lcc on lm.clubNo = lcc.clubNo "
            "left join lionsRank lr on lm.rankNo = lr.rankNo "
            "left join circleMember cm on lm.memberNo = cm.memberNo "
            "LEFT JOIN lionsRank lr2 ON cm.rankNo = lr2.rankNo "
            "where cm.circleNo = :circleno and cm.attrib = :attr order by lm.clubNo, lm.memberJoindate")
        result = await db.execute(query, {"circleno": circleno, "attr": "1000010000"})
        return result.fetchall()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Database query failed(CircleMemberLIST)")

async def get_circlememberdtl(circleno:int, memberno: int, db: AsyncSession):
    try:
        query = text("select cm.cmId, cm.circleNo, lc.circleName, cm.memberNo, lm.memberName,lr.rankNo,lr.rankTitlekor ,cm.addRemark, cm.circlePeriod from circleMember cm left join lionsMember lm on lm.memberNo = cm.memberNo left join lionsRank lr on cm.rankNo = lr.rankNo  left join lionsCircle lc on lc.circleNo = cm.circleNo where cm.memberNo = :memberno and cm.circleNo = :circleno")
        result = await db.execute(query, {"memberno": memberno,"circleno":circleno})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CircleMemberDetail)")

async def get_memberlist(db: AsyncSession):
    try:
        query = text(
            "SELECT lm.memberNo, lm.memberName, lcc.clubName, lr.rankTitlekor FROM lionsMember lm left join lionsClub lcc on lm.clubNo = lcc.clubNo "
            "left join lionsRank lr on lm.rankNo = lr.rankNo")
        result = await db.execute(query)
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(MEMBERLIST)")

async def get_rankmemberlist(rankno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsMember where rankNo = :rankno")
        result = await db.execute(query, {"rankno": rankno})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")

async def get_circlerank(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where rankDiv = :rankdiv")
        result = await db.execute(query, {"rankdiv": 'CIRCLE'})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RankCircleList)")

async def get_circledtl(circleno:int,db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsCircle where circleNo = :circleno")
        result = await db.execute(query, {"circleno": circleno})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(Circledtl)")

async def get_memberdetail(memberon: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsMember where memberNo = :memberno")
        result = await db.execute(query, {"memberno": memberon})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(regionCLUBLIST)")

async def get_clubmembercard(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lr.rankTitlekor FROM lionsMember lm LEFT join lionsRank lr on lm.rankNo = lr.rankNo where clubNo = :club_no")
        result = await db.execute(query, {"club_no": clubno})
        member_list = result.fetchall()
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
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBMemberCards)")

async def get_clubmemberlist(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT lm.*, lr.rankTitlekor FROM lionsMember lm LEFT join lionsRank lr on lm.rankNo = lr.rankNo where clubNo = :club_no order by lm.clubSortNo")
        result = await db.execute(query, {"club_no": clubno})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBMemberList)")

async def get_clubdocs(clubno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT * FROM lionsDoc where clubNo = :clubno and attrib not like :attrxx")
        result = await db.execute(query, {"clubno": clubno, "attrxx": '%XXX%'})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBDocList)")

async def get_clubdoc(docno: int, db: AsyncSession):
    try:
        query = text("SELECT cDocument from lionsDoc where docno = :docno")
        result = await db.execute(query, {"docno": docno})
        doc = result.fetchone()
        return doc[0] if doc else None
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBDoc)")

async def get_regionlist(db: AsyncSession):
    try:
        query = text(
            "SELECT lr.*, GROUP_CONCAT(lc.clubName SEPARATOR ', ') AS clubNames, lm.memberName FROM lionsaddr.lionsRegion lr "
            "LEFT JOIN lionsaddr.lionsClub lc ON lr.regionNo = lc.regionNo "
            "LEFT JOIN lionsaddr.lionsMember lm ON lr.chairmanNo = lm.memberNo "
            "where lr.attrib not like :attpatt GROUP BY lr.regionNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(DICT)")

async def get_clubstaff(clubno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsClubstaff where clubNo = :clubno and attrib not like :attrxx")
        result = await db.execute(query, {"clubno": clubno, "attrxx": '%XXX%'})
        return result.fetchone()
    except Exception:
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
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CLUBSTAFFWNAME)")


async def get_circlestaffwithname(circleno: int, db: AsyncSession):
    try:
        query = text(
            "SELECT s.logPeriod, s.slog, "
            "c.circleName AS circleName, "
            "s.presidentNo, COALESCE(pm.memberName, '공석') AS presidentName, "
            "s.secretNo, COALESCE(sm.memberName, '공석') AS secretName, "
            "s.trNo, COALESCE(tm.memberName, '공석') AS trName, "
            "s.ltNo, COALESCE(ltm.memberName, '공석') AS ltName, "
            "s.ttNo, COALESCE(ttm.memberName, '공석') AS ttName, "
            "s.prpresidentNo, COALESCE(prm.memberName, '공석') AS prpresidentName, "
            "s.firstViceNo, COALESCE(fvm.memberName, '공석') AS firstViceName, "
            "s.secondViceNo, COALESCE(svm.memberName, '공석') AS secondViceName, "
            "s.thirdViceNo, COALESCE(tvm.memberName, '공석') AS thirdViceName "
            "FROM lionsCirclestaff s "
            "LEFT JOIN lionsMember pm ON s.presidentNo = pm.memberNo "
            "LEFT JOIN lionsMember sm ON s.secretNo = sm.memberNo "
            "LEFT JOIN lionsMember tm ON s.trNo = tm.memberNo "
            "LEFT JOIN lionsMember ltm ON s.ltNo = ltm.memberNo "
            "LEFT JOIN lionsMember ttm ON s.ttNo = ttm.memberNo "
            "LEFT JOIN lionsMember prm ON s.prpresidentNo = prm.memberNo "
            "LEFT JOIN lionsMember fvm ON s.firstViceNo = fvm.memberNo "
            "LEFT JOIN lionsMember svm ON s.secondViceNo = svm.memberNo "
            "LEFT JOIN lionsMember tvm ON s.thirdViceNo = tvm.memberNo "
            "LEFT JOIN lionsCircle c ON s.circleNo = c.circleNo "
            "WHERE s.circleNo = :circleno and s.attrib not like :attrxx")
        result = await db.execute(query, {"circleno": circleno, "attrxx": '%XXX%'})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(CIRCLESTAFFWNAME)")

async def get_ranklist(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where attrib not like :attpatt and rankDiv in ('CLUB','DIST') order by orderNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")

async def get_ranklistall(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where attrib not like :attpatt order by orderNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")

async def get_ranklistcircle(db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where attrib not like :attpatt and rankDiv in ('CIRC') order by orderNo")
        result = await db.execute(query, {"attpatt": "%XXX%"})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")

async def get_userdtl(userno:int,db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsUser where userNo = :userno")
        result = await db.execute(query, {"userno": userno })
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(userdtl)")

async def get_rankdtl(rankno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsRank where rankNo = :rankNo")
        result = await db.execute(query, {"rankNo": rankno})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RANKdtl)")

async def get_boarddtl(boardno: int, db: AsyncSession):
    try:
        query = text("SELECT * FROM lionsBoard where boardNo = :boardno")
        result = await db.execute(query, {"boardno": boardno})
        return result.fetchone()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(RANK)")

async def get_requests(db: AsyncSession):
    try:
        query = text(
            "SELECT a.*, b.memberName FROM requestMessage a left join lionsMember b on a.memberNo = b.memberNo where a.attrib not like :attxxx")
        result = await db.execute(query, {"attxxx": '%XXX%'})
        return result.fetchall()
    except Exception:
        raise HTTPException(status_code=500, detail="Database query failed(REQUEST)")