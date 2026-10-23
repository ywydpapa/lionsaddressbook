# Lions Address Book

FastAPI 기반 회원 주소록 웹 앱과 모바일 API입니다. 서버 진입점은 `main.py`이며, 기존 HTML 템플릿과 정적 파일은 각각 `templates/`, `static/`에 있습니다.

## Windows에서 시작하기

PowerShell에서 프로젝트 폴더로 이동한 뒤 가상 환경을 만들고 의존성을 설치합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`.env.example`을 복사해 `.env`를 만들고 데이터베이스 접속 정보와 비밀 키를 설정합니다.

```powershell
Copy-Item .env.example .env
```

`dburl`은 `mysql+asyncmy://사용자:비밀번호@호스트:3306/데이터베이스?charset=utf8mb4` 형식이어야 합니다. 비밀번호에 `@`, `:`, `/` 같은 URL 예약 문자가 들어가면 URL 인코딩이 필요합니다. 앱은 시작 시 데이터베이스에 접속하지 않지만, 데이터베이스를 사용하는 페이지와 API를 이용하려면 MariaDB가 실행 중이고 해당 DB가 준비되어 있어야 합니다.

앱이 시작할 때 Firebase Admin SDK를 초기화하므로 Firebase 서비스 계정 JSON 파일을 `common/r15addr-firebase-adminsdk-fbsvc-87610d6413.json` 경로에 별도로 준비해야 합니다. 이 파일은 비밀 정보이므로 Git에 추가하거나 공유하지 마세요.

개발 서버를 실행합니다.

```powershell
uvicorn main:app --reload
```

- 웹 앱: <http://127.0.0.1:8000/>
- 자동 API 문서: <http://127.0.0.1:8000/docs>
- 대체 API 문서: <http://127.0.0.1:8000/redoc>

## 설정 참고

- 운영 환경에서는 `SESSION_SECRET_KEY`와 `JWT_SECRET_KEY`에 각각 충분히 길고 예측 불가능한 값을 지정하세요. `.env`와 Firebase 서비스 계정 파일은 저장소에 커밋하지 않습니다.
- 앱은 기존 구조를 유지하며 `main.py`에서 생성된 `app` 객체를 Uvicorn의 `main:app`으로 실행합니다.
