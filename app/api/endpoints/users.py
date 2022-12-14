from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import dependencies

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    response_description="The new created user",
)
def create_user(
    *,
    db: Session = Depends(dependencies.get_db),
    user_in: schemas.UserCreate,
    current_user: models.User = Depends(dependencies.get_current_active_superuser),
):
    """
    Open endpoint to creat a new user. No need to be
    logged in, anyone can create a user and then log
    in as that user to perform more actions.
    """
    user = models.User.get_by_email(db, user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = models.User.create(db, user_in)
    return user


@router.get(
    "",
    response_model=list[schemas.User],
    summary="Get a range of users",
    response_description="List of users",
)
def read_users(
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_superuser),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0),
):
    return models.User.get_multiple(db, offset=offset, limit=limit)


@router.get(
    "/me",
    response_model=schemas.User,
    summary="Get current user",
    response_description="The current user information",
)
def read_user_me(
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Get the user currently logged in.
    """

    return current_user


@router.get(
    "/{user_id}",
    response_model=schemas.User,
    summary="Get a specific user by ID",
    response_description="The user with the specified ID",
)
def read_user_by_id(
    user_id: int,
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    user = models.User.get_by_id(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # only superuser can access other users information
    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return user


@router.put(
    "/me",
    response_model=schemas.User,
    summary="Update current user",
    response_description="The updated current user",
)
def update_user_me(
    update_data: schemas.UserUpdate,
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    updated_user = models.User.update(db, current=current_user, new=update_data)
    return updated_user


@router.put(
    "/{user_id}",
    response_model=schemas.User,
    summary="Update a specific user by ID",
    response_description="The updated user with the specified ID",
)
def update_user_by_id(
    user_id: int,
    update_data: schemas.UserUpdate,
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    user = models.User.get_by_id(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # only superuser can access other users information
    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    user = models.User.update(db, current=user, new=update_data)
    return user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user",
)
def delete_user_me(
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):

    models.User.delete(db, current_user)
    # the body will be empty when using status code 204


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a specific user by ID",
)
def delete_user_by_id(
    user_id: int,
    db: Session = Depends(dependencies.get_db),
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    user = models.User.get_by_id(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # only superuser can access other users information
    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    models.User.delete(db, user)
    # the body will be empty when using status code 204
