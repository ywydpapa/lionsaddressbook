import os
import dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

dotenv.load_dotenv()
DATABASE_URL = os.getenv("dburl")

# Fix SQLAlchemy asyncmy pool_pre_ping missing argument bug
try:
    from sqlalchemy.dialects.mysql.asyncmy import AsyncAdapt_asyncmy_connection
    _orig_ping = AsyncAdapt_asyncmy_connection.ping
    def _safe_ping(self, reconnect: bool = False):
        return _orig_ping(self, False)
    AsyncAdapt_asyncmy_connection.ping = _safe_ping
except Exception:
    pass

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=1800
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

