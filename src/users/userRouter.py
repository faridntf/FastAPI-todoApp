from fastapi import(
    APIRouter,
    Depends,
    status,
    HTTPException,
    Security,
    Response
)

from core import get_db

from sqlalchemy.orm import Session
from sqlalchemy.sql import or_
from .models import UserModel
from .userService import check_user_duplicates,find_user
from .userSchema import(
    UserCreateSc,
    UserResponseSc,
)

from fastapi.security import OAuth2PasswordRequestForm
from .auth import create_access_token
from .auth.jwt_auth import set_coookie


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


@router.post("/login")
def login_user(response:Response,identifier:OAuth2PasswordRequestForm = Depends(), db : Session = Depends(get_db)):
    user = find_user(identifier.username,db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="username or email or phone number or password is incorrect")
        
    verify_password = user.verify_password(identifier.password)
    if verify_password == False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="username or email or phone number or password is incorrect")
        
    if user.is_active == False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="this account is not active")
    if user.is_delete == True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="account has deleted")
    access_token = create_access_token(user.id)
    set_coookie("access_token",access_token,response=response)
    return "login successfully"



from fastapi import Request
@router.post("/logout")
def logout_account(requ : Request,response:Response):
    print(requ.cookies)
    response.delete_cookie(key="access_token",path="/")
    return "Logout successfully"