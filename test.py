from passlib.context import CryptContext

# Bcrypt 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 'core2020' 암호화
hashed_pw = pwd_context.hash("core2020")
print(hashed_pw)
