import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# main.py에서 DB 세션 및 토큰 관련 함수 가져오기
# (순환 참조를 방지하기 위해 main.py의 하단에서 이 라우터를 등록합니다)
from main import get_db, get_current_mobile_user, create_access_token
from sqlalchemy import text, bindparam

phapp_router = APIRouter(prefix="/phapp", tags=["Mobile App"])

def row_to_dict(row):
    d = dict(row._mapping)
    for k, v in d.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            d[k] = v.isoformat()
    return d

class RequestMessage(BaseModel):
    memberNo: str
    message: str


@phapp_router.get("/clubList/{regionno}")
async def phappclublist(regionno: int, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT clubNo, clubName, regionNo FROM lionsClub where regionNo = :regionNo ")
        result = await db.execute(query, {"regionNo": regionno})
        rows = result.fetchall()
        result_data = [{"clubNo": row[0], "clubName": row[1], "regionNo": row[2]} for row in rows]
        return {"clubs": result_data}
    except Exception as e:
        print("error:", e)
        return {"clubs": []}


@phapp_router.get("/memberList/{clubno}")
async def phappmemberlist(clubno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lm.maskYN, lm.clubRank FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo where lm.clubNo = :clubno order by lm.clubSortNo, lm.memberJoindate")
        result = await db.execute(query, {"clubno": clubno})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": "비공개" if row[4] == "Y" else row[2], "rankTitle": row[3], "clubRank":row[5]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/clubdocs/{clubno}")
async def phappclubdocs(clubno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from lionsDoc where (clubNo = :clubno or clubNo = 999) and attrib not like :attrib order by clubNo desc")
        result = await db.execute(query, {"clubno": clubno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"docNo": row[0], "docType": row[2], "docTitle": row[3]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/docviewer/{docno}")
async def phappdocviewer(docno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT cDocument, docTitle from lionsDoc where docNo = :docno ")
        result = await db.execute(query, {"docno": docno})
        row = result.fetchone()
        result_data = [{"cDoc": row[0], "title": row[1]}] if row else []
        return {"doc": result_data}
    except Exception as e:
        print("error:", e)
        return {"doc": []}


@phapp_router.get("/notice/{regionno}")
async def phappnotice(regionno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from boardMessage where regionNo = :regionno and attrib not like :attrib")
        result = await db.execute(query, {"regionno": regionno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "writer": row[3], "noticeTitle": row[4]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/notice/{regionno}/{memberno}")
async def phappnotice2(regionno: int, memberno:int ,db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT a.messageNo, a.messageTitle,b.readYN, b.attendPlan from boardMessage a left join noticeAndswer b on b.noticeType = 'REGION' and a.messageNo = b.noticeNo and b.memberNo = :memberno where a.regionNo = :regionno and a.attrib not like :attrib")
        result = await db.execute(query, {"regionno": regionno,"memberno":memberno ,"attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "noticeTitle": row[1], "readYN": row[2], "attendPlan": row[3]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/clubnotice/{clubno}")
async def phappcnotice(clubno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from clubboardMessage where clubNo = :clubno and attrib not like :attrib")
        result = await db.execute(query, {"clubno": clubno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "writer": row[3], "noticeTitle": row[4]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/circlenotice/{memberno}")
async def phappcirnotice(memberno: int, db: AsyncSession = Depends(get_db),
                         current_user: str = Depends(get_current_mobile_user)):
    try:
        # 1. 사용자가 속한 써클 목록 조회
        query1 = text("""
                      SELECT a.circleNo, b.circleName
                      FROM circleMember a
                               LEFT JOIN lionsCircle b ON a.circleNo = b.circleNo
                      WHERE a.memberNo = :memberno
                        AND a.attrib NOT LIKE :attrib
                      """)
        result1 = await db.execute(query1, {"memberno": memberno, "attrib": "%XXX%"})
        rows1 = result1.fetchall()

        if not rows1:
            return {"docs": [], "circlenames": []}

        circle_nos = [row[0] for row in rows1]
        circle_names = [row[1] for row in rows1]

        # 써클 번호로 써클 이름을 찾기 위한 딕셔너리
        circle_dict = {row[0]: row[1] for row in rows1}

        # 2. 써클 공지사항 목록 및 읽음 여부 조회
        # 🌟 c.* 대신 필요한 컬럼(messageNo, circleNo, writer, noticeTitle)을 명시적으로 지정
        query2 = text("""
                      SELECT c.messageNo,
                             c.circleNo,
                             c.writerNo,
                             c.messageTitle,
                             CASE WHEN r.noticeNo IS NOT NULL THEN 'Y' ELSE 'N' END AS readYN
                      FROM circleboardMessage c
                               LEFT JOIN noticeAndswer r
                                         ON c.messageNo = r.noticeNo
                                             AND r.memberNo = :memberno
                                             AND r.noticeType = 'CIRCLE'
                      WHERE c.circleNo IN :circlenos
                        AND c.attrib NOT LIKE :attrib
                      """)
        query2 = query2.bindparams(bindparam('circlenos', expanding=True))
        result2 = await db.execute(query2, {"circlenos": circle_nos, "attrib": "%XXX%", "memberno": memberno})
        rows2 = result2.fetchall()

        result_data = []
        for row in rows2:
            result_data.append({
                "noticeNo": row[0],  # c.messageNo
                "circleName": circle_dict.get(row[1], ""),  # c.circleNo (이제 무조건 매칭됨!)
                "writer": row[2],  # c.writer
                "noticeTitle": row[3],  # c.noticeTitle
                "readYN": row[4]  # readYN (명시된 5번째 컬럼)
            })

        return {"docs": result_data, "circlenames": circle_names}

    except Exception as e:
        print("error:", e)
        return {"docs": [], "circlenames": []}


@phapp_router.get("/clubnotice/{clubno}/{memberno}")
async def phappcnotice2(clubno: int,memberno:int ,db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT a.messageNo, a.messageTitle,b.readYN, b.attendPlan from clubboardMessage a left join noticeAndswer b on b.noticeType = 'CLUB' and a.messageNo = b.noticeNo and b.memberNo = :memberno where a.clubNo = :clubno and a.attrib not like :attrib")
        result = await db.execute(query, {"clubno": clubno,"memberno":memberno ,"attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "noticeTitle": row[1], "readYN": row[2], "attendPlan": row[3]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/clubnoticeViewer/{messageno}")
async def phappcnoticev(messageno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from clubboardMessage where messageNo = :messageno and attrib not like :attrib")
        result = await db.execute(query, {"messageno": messageno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "answerType": row[3], "noticeTitle": row[4], "noticeCont": row[5]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/circlenoticeViewer/{messageno}")
async def phappcircnoticev(messageno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from circleboardMessage where messageNo = :messageno and attrib not like :attrib")
        result = await db.execute(query, {"messageno": messageno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "answerType": row[3], "noticeTitle": row[5], "noticeCont": row[6]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/noticeViewer/{messageno}")
async def phappnoticev(messageno: int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT * from boardMessage where messageNo = :messageno and attrib not like :attrib")
        result = await db.execute(query, {"messageno": messageno, "attrib": "%XXX%"})
        rows = result.fetchall()
        result_data = [{"noticeNo": row[0], "answerType": row[3], "noticeTitle": row[4], "noticeCont": row[5]} for row in rows]
        return {"docs": result_data}
    except Exception as e:
        print("error:", e)
        return {"docs": []}


@phapp_router.get("/rmemberList/")
async def phapprmemberlist_all(db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName, lm.maskYN FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo where lm.rankNo != :rankno order by lm.memberJoindate ")
        result = await db.execute(query, {"rankno": 19})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": "비공개" if row[5] in ("Y","T") else row[2], "rankTitle": row[3], "clubName": row[4]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/rnkmemberList/{regionno}")
async def phapprnkmemberlist(regionno:int,db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName, lm.maskYN FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo where lm.rankNo != :rankno and lc.regionNo = :regionno order by lc.clubNo, lr.orderNo, lm.memberJoindate ")
        result = await db.execute(query, {"rankno": 19, "regionno": regionno})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": "비공개" if row[5] in ("Y","T") else row[2], "rankTitle": row[3], "clubName": row[4]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/searchmember/{keywd}")
async def phappsearchmember(keywd: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        keywd = f"%{keywd}%"
        query = text("SELECT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo left join memberBusiness mb on lm.memberNo = mb.memberNo where lm.memberName like :keyword or lm.memberPhone like :keyword or lm.memberAddress like :keyword or lm.memberEmail like :keyword or lm.addMemo like :keyword or lm.officeAddress like :keyword or mb.bisTitle like :keyword or mb.bisType like :keyword or mb.bistypeTitle like :keyword or mb.bisMemo like :keyword order by lm.memberJoindate")
        result = await db.execute(query, {"keyword": keywd})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": row[2], "rankTitle": row[3], "clubName": row[4]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/rsearchmember/{regionno}/{keywd}")
async def phapprsearchmember(regionno:int, keywd: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        keywd = f"%{keywd}%"
        query = text("SELECT DISTINCT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName, lm.maskYN FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo left join memberBusiness mb on lm.memberNo = mb.memberNo where lc.regionNo = :regionno AND (lm.memberName like :keyword or lm.memberPhone like :keyword or lm.memberAddress like :keyword or lm.memberEmail like :keyword or lm.addMemo like :keyword or lm.officeAddress like :keyword or mb.bisTitle like :keyword or mb.bisType like :keyword or mb.bistypeTitle like :keyword or mb.bisMemo like :keyword) order by lm.memberJoindate")
        result = await db.execute(query, {"keyword": keywd, "regionno":regionno})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": "비공개" if row[5] in ("Y","T") else row[2], "rankTitle": row[3], "clubName": row[4]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/csearchmember/{clubno}/{keywd}")
async def phappcsearchmember(clubno:int, keywd: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        keywd = f"%{keywd}%"
        query = text("SELECT DISTINCT lm.memberNo, lm.memberName, lm.memberPhone, lr.rankTitlekor, lc.clubName, lm.maskYN, lm.clubRank FROM lionsMember lm left join lionsRank lr on lm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo left join memberBusiness mb on lm.memberNo = mb.memberNo where lc.clubNo = :clubno AND (lm.memberName like :keyword or lm.memberPhone like :keyword or lm.memberAddress like :keyword or lm.memberEmail like :keyword or lm.addMemo like :keyword or lm.officeAddress like :keyword or mb.bisTitle like :keyword or mb.bisType like :keyword or mb.bistypeTitle like :keyword or mb.bisMemo like :keyword) order by lm.memberJoindate")
        result = await db.execute(query, {"keyword": keywd, "clubno":clubno})
        rows = result.fetchall()
        result_data = [{"memberNo": row[0], "memberName": row[1], "memberPhone": "비공개" if row[5] in ("Y","T") else row[2], "rankTitle": row[3], "clubName": row[4], "clubRank":row[6]} for row in rows]
        return {"members": result_data}
    except Exception as e:
        print("error:", e)
        return {"members": []}


@phapp_router.get("/memberDtl/{memberno}")
async def phappmemberdtl(memberno: int, db: AsyncSession = Depends(get_db),
                         current_user: str = Depends(get_current_mobile_user)):
    try:
        # 사진 관련 무거운 JOIN과 TO_BASE64 제거, 매핑을 위해 컬럼명 명시
        query = text("""
                     SELECT lm.memberNo,
                            lm.memberName,
                            lm.memberMF,
                            CASE
                                WHEN DATE_FORMAT(lm.memberBirth, '%Y') = '2029' THEN ''
                                WHEN DATE_FORMAT(lm.memberBirth, '%m-%d') = '01-01'
                                    THEN CONCAT(DATE_FORMAT(lm.memberBirth, '%Y'), '년생')
                                ELSE DATE_FORMAT(lm.memberBirth, '%Y-%m-%d') END AS memberBirth,
                            lm.memberSeccode,
                            lm.memberAddress,
                            lm.memberPhone,
                            lm.memberEmail,
                            lm.memberJoindate,
                            lm.clubNo,
                            lm.sponserNo,
                            lm.addMemo,
                            lm.rankNo,
                            lm.officeAddress,
                            lm.spouseName,
                            lm.spousePhone,
                            CASE
                                WHEN DATE_FORMAT(lm.spouseBirth, '%Y') = '2020' THEN ''
                                WHEN DATE_FORMAT(lm.spouseBirth, '%m-%d') = '01-01'
                                    THEN CONCAT(DATE_FORMAT(lm.spouseBirth, '%Y'), '년생')
                                ELSE DATE_FORMAT(lm.spouseBirth, '%Y-%m-%d') END AS spouseBirth,
                            lm.maskYN,
                            lm.funcNo,
                            lr.rankTitlekor,
                            lc.clubName,
                            mb.bisTitle,
                            mb.bisRank,
                            mb.bisType,
                            mb.bistypeTitle,
                            mb.officeTel                                         as offtel,
                            mb.officeAddress                                     as offAddress,
                            mb.officeEmail                                       as offEmail,
                            mb.officePostNo                                      as offPost,
                            mb.officeWeb                                         as offWeb,
                            mb.officeSns                                         as offSns,
                            mb.bisMemo,
                            lm.clubRank
                     FROM lionsMember lm
                              LEFT JOIN lionsRank lr ON lm.rankNo = lr.rankNo
                              LEFT JOIN lionsClub lc ON lm.clubNo = lc.clubNo
                              LEFT JOIN memberBusiness mb ON lm.memberNo = mb.memberNo and mb.attrib not like '%XXX%'
                     WHERE lm.memberNo = :memberno
                     """)
        result = await db.execute(query, {"memberno": memberno})
        row = result.fetchone()
        if not row: return {"memberdtl": []}

        # DB 인덱스 에러 방지를 위해 딕셔너리로 매핑
        d = dict(row._mapping)

        # 파일 존재 여부 확인 후 URL 생성 (도메인이 필요하다면 앞에 추가)
        import os
        mphoto_url = f"/static/img/members/mphoto_{memberno}.png" if os.path.exists(
            f"./static/img/members/mphoto_{memberno}.png") else ""
        ncard_url = f"/static/img/members/ncard_{memberno}.png" if os.path.exists(
            f"./static/img/members/ncard_{memberno}.png") else ""
        sphoto_url = f"/static/img/members/sphoto_{memberno}.png" if os.path.exists(
            f"./static/img/members/sphoto_{memberno}.png") else ""

        mask = d.get("maskYN", "N")

        # 모바일 앱 호환성을 위해 키 이름(mPhotoBase64 등)은 그대로 유지하되, 값은 URL을 넣습니다.
        res = {
            "memberNo": d["memberNo"], "memberName": d["memberName"], "memberPhone": d["memberPhone"],
            "mPhotoBase64": mphoto_url, "clubNo": d["clubNo"], "rankTitle": d["rankTitlekor"],
            "memberMF": d["memberMF"], "memberAddress": d["memberAddress"], "memberEmail": d["memberEmail"],
            "memberJoindate": d["memberJoindate"], "addMemo": d["addMemo"], "memberBirth": d["memberBirth"],
            "clubName": d["clubName"], "nameCard": ncard_url, "officeAddress": d["officeAddress"],
            "spouseName": d["spouseName"], "spousePhone": d["spousePhone"], "spouseBirth": d["spouseBirth"],
            "spousePhoto": sphoto_url, "bisTitle": d["bisTitle"], "bisRank": d["bisRank"],
            "bisType": d["bisType"], "bistypeTitle": d["bistypeTitle"], "offtel": d["offtel"],
            "offAddress": d["offAddress"], "offEmail": d["offEmail"], "offPost": d["offPost"],
            "offWeb": d["offWeb"], "offSns": d["offSns"], "bisMemo": d["bisMemo"], "clubRank": d["clubRank"]
        }

        # 마스킹(비공개) 처리 로직
        if mask == 'S':
            res.update({"memberAddress": "비공개", "memberBirth": "비공개"})
        elif mask == 'T':
            res.update({
                "memberAddress": "비공개", "memberEmail": "비공개", "memberJoindate": "비공개",
                "memberBirth": "비공개", "spouseName": "비공개", "spousePhone": "비공개",
                "spouseBirth": "비공개", "spousePhoto": ""
            })
        elif mask not in ('N', 'S', 'T'):  # 완전 비공개
            res.update({
                "memberPhone": "비공개", "memberAddress": "비공개", "memberEmail": "비공개",
                "memberJoindate": "비공개", "addMemo": "비공개", "memberBirth": "비공개",
                "nameCard": "", "officeAddress": "비공개", "spouseName": "비공개",
                "spousePhone": "비공개", "spouseBirth": "비공개", "spousePhoto": "",
                "bisTitle": "비공개", "bisRank": "비공개", "bisType": "비공개",
                "bistypeTitle": "비공개", "offtel": "비공개", "offAddress": "비공개",
                "offEmail": "비공개", "offPost": "비공개", "offWeb": "비공개",
                "offSns": "비공개", "bisMemo": "비공개"
            })

        return {"memberdtl": [res]}
    except Exception as e:
        print("Member Detail error:", e)
        return {"memberdtl": []}


@phapp_router.get("/zlogin/{phoneno}")
async def phappzlogin(phoneno: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT lm.clubNo, lm.memberNo, lc.regionNo from lionsMember lm left join lionsClub lc on lc.clubNo = lm.clubNo where lm.memberSeccode = :phoneno")
        result = await db.execute(query, {"phoneno": phoneno})
        rows = result.fetchone()
        if rows is None: return {"error": "No data found for the given phone number."}
        return {"clubno": rows[0], "memberno": rows[1], "regionno": rows[2]}
    except Exception as e:
        print("mLogin error:", e)
        return {"error": "Login error"}


@phapp_router.get("/xlogin/{phoneno}")
async def phappxlogin(phoneno: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("SELECT lm.clubNo, lm.memberNo, lc.regionNo, lm.funcNo, lc.clubName from lionsMember lm left join lionsClub lc on lc.clubNo = lm.clubNo where lm.memberSeccode = :phoneno")
        result = await db.execute(query, {"phoneno": phoneno})
        rows = result.fetchone()
        if rows is None: return {"error": "No data found for the given phone number."}

        access_token = create_access_token(data={"sub": str(rows[1])})
        return {
            "clubno": rows[0], "memberno": rows[1], "regionno": rows[2],
            "funcno": rows[3], "clubname": rows[4], "access_token": access_token
        }
    except Exception as e:
        print(f"mLogin error: {e}")
        return {"error": "Login error"}


@phapp_router.post("/requestmessage")
async def phapprequest_message(req: RequestMessage, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("INSERT INTO requestMessage (memberNo, message) VALUES (:memberNo, :message)")
        await db.execute(query, {"memberNo": req.memberNo, "message": req.message})
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("request_message error:", e)
        raise HTTPException(status_code=500, detail="DB 저장 중 오류 발생")


@phapp_router.post("/maskYN/{memberno}/{msk}")
async def phappmaskyn(memberno:int, msk:str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("UPDATE lionsMember set maskYN = :msk where memberNo = :memberNo")
        await db.execute(query, {"memberNo": memberno , "msk": msk})
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("maskYN error:", e)
        raise HTTPException(status_code=500, detail="DB 저장 중 오류 발생")


@phapp_router.post("/funcNo/{memberno}/{funcno}")
async def phappupdatefuncno(memberno:int, funcno:int, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("UPDATE lionsMember set funcNo = :func where memberNo = :memberNo")
        await db.execute(query, {"memberNo": memberno , "func": funcno})
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("funcNo error:", e)
        raise HTTPException(status_code=500, detail="DB 저장 중 오류 발생")


@phapp_router.post("/noticeRead/{memberno}/{noticeno}/{noticetype}")
async def phappreadnot(memberno: int, noticeno: int, noticetype: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        check_query = text("SELECT 1 FROM noticeAndswer WHERE memberNo = :memberNo AND noticeNo = :notno AND noticeType = :nottype LIMIT 1")
        result = await db.execute(check_query, {"memberNo": memberno, "notno": noticeno, "nottype": noticetype})
        exists = result.scalar() is not None
        if not exists:
            insert_query = text("INSERT INTO noticeAndswer (memberNo, noticeNo, noticeType, readYN) VALUES (:memberNo, :notno, :nottype, 'Y')")
            await db.execute(insert_query, {"memberNo": memberno, "notno": noticeno, "nottype": noticetype})
            await db.commit()
            return {"status": "success"}
        else:
            return {"status": "already_exists"}
    except Exception as e:
        print("noticeRead error:", e)
        raise HTTPException(status_code=500, detail="공지 읽음 처리 오류 발생")


@phapp_router.post("/noticeAttend/{memberno}/{noticeno}/{noticetype}/{attend}")
async def phappattendnot(memberno:int, noticeno:int, noticetype:str, attend:str ,db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("update noticeAndswer set attendPlan = :attend where memberNo = :memberNo and noticeNo = :notno and noticeType = :nottype")
        await db.execute(query, {"memberNo": memberno, "notno": noticeno, "nottype": noticetype, "attend": attend })
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        print("noticeAttend error:", e)
        raise HTTPException(status_code=500, detail="공지 참석 처리 오류 발생")


@phapp_router.get("/getmask/{memberno}")
async def phappgetmask(memberno:int,db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("select maskYN from lionsMember where memberNo = :memberNo")
        result = await db.execute(query, {"memberNo": memberno })
        rows = result.fetchone()
        return {"maskYN": rows[0]} if rows else {"maskYN": None}
    except Exception as e:
        print("getmask error:", e)


@phapp_router.get("/getfuncno/{memberno}")
async def phappgetfuncno(memberno: int, db: AsyncSession = Depends(get_db),
                         current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text("select funcNo from lionsMember where memberNo = :memberNo")
        result = await db.execute(query, {"memberNo": memberno})
        rows = result.fetchone()
        return {"funcno": rows[0]} if rows else {"funcno": None}
    except Exception as e:
        print("getfuncno error:", e)


@phapp_router.get("/getmycircle/{memberno}")
async def phappgetmycircle(memberno: int, db: AsyncSession = Depends(get_db),
                           current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text(
            "select cm.circleNo, lc.circleName  from circleMember cm left join lionsCircle lc on cm.circleNo = lc.circleNo where cm.memberNo = :memberno ")
        result = await db.execute(query, {"memberno": memberno})
        rows = result.fetchall()
        circles = [dict(row._mapping) for row in rows]
        return {"circles": circles}
    except Exception as e:
        print("getmycircle error:", e)


@phapp_router.get("/getcirclemembers/{circleno}")
async def phappgetcirclemembers(circleno: int, db: AsyncSession = Depends(get_db),
                                current_user: str = Depends(get_current_mobile_user)):
    try:
        query = text(
            "select cm.memberNo , lm.memberName, lc.clubName , lr.rankTitlekor, lm.memberPhone  from circleMember cm left join lionsMember lm on cm.memberNo = lm.memberNo left join lionsRank lr on cm.rankNo = lr.rankNo left join lionsClub lc on lm.clubNo = lc.clubNo where cm.circleNo = :circleno order by lr.orderNo, lc.clubNo")
        result = await db.execute(query, {"circleno": circleno})
        rows = result.fetchall()
        cmembers = [dict(row._mapping) for row in rows]
        return {"cmembers": cmembers}
    except Exception as e:
        print("getcirclemembers error:", e)
