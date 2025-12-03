from fastapi import APIRouter, Depends

from .. import schemas
from ..dependencies import get_current_user
from ..models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

