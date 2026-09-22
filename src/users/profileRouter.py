from fastapi import(
    APIRouter,
    Depends,
    status,
    HTTPException,
    Security,
    UploadFile,
)

from .profSchema import (
    ProfileCreateSc,
    ProfileResponseSc,
    ProfileUpdateSc
)

from .profileService import (
    duplicate_data_NID,
    duplicate_data_UID,
    upload_avatar,
    delete_old_profile_avatar
)

from core import get_db
from sqlalchemy.orm import Session
from sqlalchemy.sql import or_
from sqlalchemy.exc import SQLAlchemyError
from .models import UserModel
from .models import ProfileModel
from .userService import get_current_user

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    redirect_slashes=True
)

@router.patch("/my-profile")
def update_profile_detail(profile_data:ProfileUpdateSc, db:Session=Depends(get_db),current_user : UserModel = Depends(get_current_user)):
    profile = db.query(ProfileModel).filter(ProfileModel.user_id_fk == current_user.id).one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    duplicate_data_NID(profile_data.national_id,db=db)
    update_data = profile_data.model_dump(exclude_unset=True, exclude=["website"])
    for key, value in update_data.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile

@router.post("my-profile",status_code=status.HTTP_201_CREATED)
def upload_profile_avatar(data : UploadFile, db : Session = Depends(get_db),current_user : UserModel = Depends(get_current_user)):
    avatar_path = upload_avatar(
        data=data,
        current_user_id=current_user.id,
    )
    profile = (
        db.query(ProfileModel)
        .filter(ProfileModel.user_id_fk == current_user.id)
        .one_or_none()
    )
    stored_path = f"uploads/profiles/{avatar_path.name}"
    try:
        if profile is None:
            profile = ProfileModel(
                user_id_fk=current_user.id,
                profile_url=stored_path,
            )
            db.add(profile)
        else:
            old_profile_path = profile.profile_url
            profile.profile_url = stored_path
        db.commit()
        delete_old_profile_avatar(old_profile_path)
        
    except SQLAlchemyError:
        db.rollback()
        try:
            avatar_path.unlink(missing_ok=True)
        except OSError as e:
            print(e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="unknown error")

        raise HTTPException(
            status_code=500,
            detail="this profile doesnt upload",
        )

    return "upload profile was successfully"

@router.post("/my-profile")
def create_new_profile(
    profile_data: ProfileCreateSc,
    db: Session = Depends(get_db),
    current_user_data: UserModel = Depends(get_current_user),
):
    
    duplicateUID = duplicate_data_UID(current_user_data.id,db)
    duplicateNID = duplicate_data_NID(profile_data.national_id,db)
    
    if duplicateNID is None and duplicateUID is None:
        detail = profile_data.model_dump(exclude_unset=True,exclude=["website"])
        set_profile = ProfileModel(**detail)
        set_profile.user_id_fk = current_user_data.id
        try:
            db.add(set_profile)
            current_user_data.is_profile_completed = True
            db.commit()
            db.refresh(set_profile)
            return set_profile
        except:
            db.rollback()
    
@router.get("/my-profile",response_model=ProfileResponseSc,status_code=status.HTTP_200_OK)
def show_my_profile(
    db : Session = Depends(get_db),
    current_user_data = Depends(get_current_user)
):
    user_profile_data = db.query(ProfileModel).filter(ProfileModel.user_id_fk == current_user_data.id).one_or_none()
    if user_profile_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Attention! Please complete your profile.")
    return user_profile_data