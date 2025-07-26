import os
import requests
from bs4 import BeautifulSoup

# 사용자 정보 입력
USER_ID = "김동진"
USER_PW = "4290642"

BASE_URL = "http://lc355a.or.kr"
LOGIN_URL = f"{BASE_URL}/bbs/login.php"
LIST_URL = f"{BASE_URL}/bbs/content.php?co_id=ready01&club_sch=29"
SAVE_DIR = "member_photos"
os.makedirs(SAVE_DIR, exist_ok=True)

# 세션 생성
session = requests.Session()

# 1. 로그인 (폼 파라미터명은 실제 HTML에서 확인 필요)
login_data = {
    "mb_id": USER_ID,
    "mb_password": USER_PW,
}
res = session.post(LOGIN_URL, data=login_data)
res.raise_for_status()

# 로그인 성공여부는 메인페이지 등에서 확인 가능
main_page = session.get(BASE_URL)
if USER_ID in main_page.text:
    print("로그인 성공")
else:
    print("로그인 실패: 아이디/비밀번호 확인 필요")
    exit()

# 2. 회원 리스트 페이지 접근
res = session.get(LIST_URL)
res.raise_for_status()
soup = BeautifulSoup(res.text, "html.parser")

# 3. 회원별 상세페이지 링크 추출
links = soup.select('a[href*="mb_no="]')
members = []
for link in links:
    href = link.get('href')
    name = link.get_text(strip=True)
    if "mb_no=" in href:
        mb_no = href.split("mb_no=")[1].split("&")[0]
        members.append({"name": name, "mb_no": mb_no})

print(f"총 {len(members)}명 회원 발견")

# 4. 상세페이지에서 사진 추출 및 저장
for member in members:
    detail_url = f"{BASE_URL}/bbs/content.php?co_id=ready01&mb_no={member['mb_no']}&club_sch=29"
    res = session.get(detail_url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # img 태그 위치에 따라 조정 필요
    img = soup.find("img")
    if img and img.get("src"):
        img_url = img["src"]
        if not img_url.startswith("http"):
            img_url = BASE_URL + img_url
        img_data = session.get(img_url).content
        # 파일명에 사용할 수 없는 문자는 _로 대체
        safe_name = "".join([c if c.isalnum() else "_" for c in member['name']])
        filename = os.path.join(SAVE_DIR, f"{safe_name}.jpg")
        with open(filename, "wb") as f:
            f.write(img_data)
        print(f"{member['name']} 사진 저장 완료")
    else:
        print(f"{member['name']} 사진 없음")
