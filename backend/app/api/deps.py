from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import read_token
from app.db.database import SessionLocal
from app.db.models import User

bearer = HTTPBearer(auto_error=False)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id = read_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dependency
