import hashlib
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(
        password,
        hashed_password,
    )

    

def hash_session_token(token: str):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()