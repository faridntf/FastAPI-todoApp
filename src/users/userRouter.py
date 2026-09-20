from fastapi import APIRouter,Depends,status,HTTPException

from core import get_db

from sqlalchemy.orm import Session
from sqlalchemy.sql import or_
from .models import UserModel
from .userService import check_user_duplicates,find_user
from .userSchema import(
    UserCreateSc,
    UserResponseSc,
    UserLoginSc
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    redirect_slashes=True
)

@router.post("register",response_model=UserResponseSc,status_code=status.HTTP_201_CREATED)
def create_user(data : UserCreateSc, db: Session = Depends(get_db)):
    check_user_duplicates(db,data)
    user_data = data.model_dump(exclude=["re_password","password"])
    new_user = UserModel(**user_data)
    new_user.set_password(data.password)
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except:
        db.rollback()


@router.post("/login",response_model=UserResponseSc)
def login_user(identifier:UserLoginSc, db : Session = Depends(get_db)):
    user = find_user(identifier.identifier,db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="username or email or phone number or password is incorrect")
    verify_password = user.verify_password(identifier.password)
    if verify_password == False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="username or email or phone number or password is incorrect")
    return user