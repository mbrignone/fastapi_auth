from unittest.mock import ANY, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_account_verification_token
from app.models import User
from app.tests.factories import UserFactory
from app.tests.fixtures import mock_email  # noqa: F401


def test_get_access_token_valid(
    client: TestClient,
    db_session: Session,
    auth_headers: tuple[dict[str, str], User],
    auth_headers_superuser: tuple[dict[str, str], User],
):
    headers, user = auth_headers_superuser
    user_data = {"email": "test@test.com", "password": "123456"}

    response = client.post("/api/users", json=user_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    form_data = {"username": user_data["email"], "password": user_data["password"]}
    response = client.post("api/token", data=form_data)

    assert response.status_code == status.HTTP_201_CREATED

    token = response.json()
    assert "access_token" in token
    assert "refresh_token" in token
    assert token["token_type"] == "bearer"


@pytest.mark.parametrize("cases", ["incorrect", "inactive"])
def test_get_access_token_invalid(
    client: TestClient,
    db_session: Session,
    cases: str,
    auth_headers_superuser: tuple[dict[str, str], User],
):
    headers, user = auth_headers_superuser
    user_data = {"email": "test@test.com", "password": "123456"}

    response = client.post("/api/users", json=user_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    form_data = {"username": user_data["email"], "password": user_data["password"]}
    if cases == "incorrect":
        form_data["password"] = "wrong_password"
    else:
        db_user = User.get_by_email(db_session, email=user_data["email"])
        db_user.is_active = False

    response = client.post("api/token", data=form_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    if cases == "incorrect":
        assert response.json() == {"detail": "Incorrect email or password"}
    else:
        assert response.json() == {"detail": "Inactive user"}


def test_get_refresh_token_valid(
    client: TestClient,
    db_session: Session,
    auth_headers_superuser: tuple[dict[str, str], User],
):
    headers, user = auth_headers_superuser
    user_data = {"email": "test@test.com", "password": "123456"}
    response = client.post("/api/users", json=user_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    form_data = {"username": user_data["email"], "password": user_data["password"]}
    response = client.post("api/token", data=form_data)
    assert response.status_code == status.HTTP_201_CREATED

    token = response.json()
    data = {"grant_type": "refresh_token", "token": token["refresh_token"]}
    response = client.post("api/refresh_token", json=data)

    assert response.status_code == status.HTTP_201_CREATED

    token = response.json()
    assert "access_token" in token
    assert "refresh_token" not in token
    assert token["token_type"] == "bearer"


@pytest.mark.parametrize("cases", ["invalid_refresh_token", "user_not_found"])
def test_get_refresh_token_invalid(
    client: TestClient,
    db_session: Session,
    cases: str,
    auth_headers_superuser: tuple[dict[str, str], User],
):
    headers, user = auth_headers_superuser
    user_data = {"email": "test@test.com", "password": "123456"}
    response = client.post("/api/users", json=user_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    form_data = {"username": user_data["email"], "password": user_data["password"]}
    response = client.post("api/token", data=form_data)
    assert response.status_code == status.HTTP_201_CREATED

    token = response.json()
    data = {"grant_type": "refresh_token", "token": token["refresh_token"]}
    if cases == "invalid_refresh_token":
        data["grant_type"] = "not_refresh_token"
    else:
        # user_not_found case
        db_user = User.get_by_email(db_session, email=user_data["email"])
        User.delete(db_session, db_user)

    response = client.post("api/refresh_token", json=data)

    if cases == "invalid_refresh_token":
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "Invalid refresh token"}
    else:
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "User not found"}


def test_register_user(
    client: TestClient,
    db_session: Session,
    mock_email: MagicMock,  # noqa: F811
):

    data = {
        "email": "user@example.com",
        "password": "123456",
        "full_name": "Random Name",
    }

    response = client.post("/api/register", json=data)

    assert response.status_code == status.HTTP_201_CREATED

    created_user = response.json()
    db_user = User.get_by_email(db_session, email=data["email"])

    assert db_user
    data.pop("password")
    for field in data.keys():
        # check response and original data match
        assert created_user[field] == data[field]
        # check user in DB and original data match
        assert getattr(db_user, field) == data[field]

    assert db_user.is_active
    assert created_user.get("is_active")
    assert not db_user.is_verified
    assert not created_user.get("is_verified")
    assert "time_created" in created_user

    mock_email.assert_called_once_with(
        db_user.email, f"Account Verification for user {db_user.email}", ANY
    )


def test_register_user_email_disabled(client: TestClient, db_session: Session):
    data = {
        "email": "user@example.com",
        "password": "123456",
        "full_name": "Random Name",
    }

    response = client.post("/api/register", json=data)

    assert response.status_code == status.HTTP_201_CREATED

    created_user = response.json()
    db_user = User.get_by_email(db_session, email=data["email"])

    assert db_user
    assert db_user.is_verified
    assert created_user.get("is_verified")


def test_register_user_existing_email(client: TestClient, db_session: Session):
    user = UserFactory.create()

    data = {"email": user.email, "password": "123456"}
    response = client.post("/api/register", json=data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Email already registered"}


def test_current_user_invalid(client: TestClient, db_session: Session):
    auth_token = "invalid_token_string"
    headers = {"Authorization": f"Bearer {auth_token}"}

    response = client.get("/api/users/me", headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Could not validate credentials"}


def test_current_user_non_existent(
    client: TestClient,
    db_session: Session,
    auth_headers: tuple[dict[str, str], User],
):
    headers, user = auth_headers

    User.delete(db_session, db_obj=user)

    response = client.get("/api/users/me", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "User not found"}


def test_current_user_inactive(
    client: TestClient,
    db_session: Session,
    auth_headers: tuple[dict[str, str], User],
):
    headers, user = auth_headers

    User.update(db_session, current=user, new={"is_active": False})

    response = client.get("/api/users/me", headers=headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Inactive user"}


def test_verify_account(client: TestClient, db_session: Session):
    user = UserFactory.create(is_verified=False)

    token = create_account_verification_token(user.email)
    verify_data = {"token": token}
    response = client.post("api/verify_account", json=verify_data)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "User verified"}
    assert user.is_verified


def test_verify_account_not_found(client: TestClient, db_session: Session):
    user = UserFactory.create(is_verified=False)

    token = create_account_verification_token(user.email)
    verify_data = {"token": token}
    User.delete(db_session, user)
    response = client.post("api/verify_account", json=verify_data)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "No user registered with that email"}
