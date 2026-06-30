import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from pydantic import BaseModel

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class FirebaseUser(BaseModel):
    """Authenticated user identity extracted from a verified Firebase ID token."""

    uid: str
    email: str | None = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> FirebaseUser:
    """FastAPI dependency to extract and verify the Firebase ID Token from authorization headers."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials
    try:
        # Verify the ID token using the Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        
        # Sanitize and validate uid format to prevent filter injection
        if not uid or not isinstance(uid, str) or not all(c.isalnum() or c in "-_" for c in uid):
            logger.warning("Invalid Firebase uid detected: %s", uid)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user identity format",
            )
            
        from backend.utils.logging_context import user_id_var
        user_id_var.set(uid)
            
        return FirebaseUser(
            uid=uid,
            email=decoded_token.get("email"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
        ) from exc
