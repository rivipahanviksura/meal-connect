from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def require_verified_organization(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_access_token(token)

        if payload.get("status") != "verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "ORGANIZATION_NOT_VERIFIED",
                        "message": "Your organization account must be verified to perform this action.",
                        "fields": []
                    }
                }
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token", "fields": []}}
        )