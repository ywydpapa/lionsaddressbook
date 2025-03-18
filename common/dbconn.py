import asyncmy
from fastapi import Depends
import dotenv, os


dotenv.load_dotenv()

DATABASE_CONFIG = {
    "host": os.getenv("host"),
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "database": os.getenv("database"),
}

async def get_connection():
    connection = None  # connection 초기화
    try:
        print("MariaDB 연결 시도 중...")  # 연결 시도 로그
        connection = await asyncmy.connect(**DATABASE_CONFIG)
        print("MariaDB 연결 성공")  # 연결 성공 로그
        yield connection
    except Exception as e:
        print(f"MariaDB 연결 실패: {e}")  # 연결 실패 로그
        raise e
    finally:
        if connection:
            try:
                print("MariaDB 연결 닫기 시도 중...")  # 연결 닫기 로그
        #        await connection.close()
                print("MariaDB 연결 닫힘")  # 연결 닫힘 로그
            except Exception as close_error:
                print(f"MariaDB 연결 닫기 중 에러 발생: {close_error}")  # 연결 닫기 에러 로그
