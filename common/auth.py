from fastapi import HTTPException, status
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def authenticate_user(username: str, password: str, connection):
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT userName, userPassword FROM lionsUser WHERE userName = %s", (username,))
        user = await cursor.fetchone()
        print(f"SQL 실행 결과: {user}")  # SQL 결과 로그
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        if not verify_password(password, user[1]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        print("사용자 ",user[0])
        return {"username": user[0]}
