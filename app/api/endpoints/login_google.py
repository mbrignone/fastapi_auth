from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware

from app import models, schemas
from app.api import dependencies
from app.core.config import get_settings

from .login import _check_active_user_exists, _generate_token_response

google_auth_app = FastAPI()

# add Session middleware so Authlib can access the request session
google_auth_app.add_middleware(SessionMiddleware, secret_key=get_settings().SECRET_KEY)


def setup_google_oauth(settings):
    config_data = {
        "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
    }
    starlette_config = Config(environ=config_data)

    oauth = OAuth(starlette_config)
    oauth.register(
        name="google",
        server_metadata_url=(
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )

    return oauth


oauth = setup_google_oauth(get_settings())


@google_auth_app.get("/login_google")
async def login_google(request: Request):
    redirect_uri = request.url_for("get_access_token_from_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


# this endpoint must match an Authorized redirect URI in Google Cloud
@google_auth_app.get(
    "/token_google",
    response_model=schemas.token.Token,
    summary="Validate Google token and get a new API access token",
    response_description="The access token",
)
async def get_access_token_from_google(
    request: Request,
    db: Session = Depends(dependencies.get_db),
):
    """
    Get an OAuth2 access token from a user logging with Google,
    to use in future requests as an authenticated user.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = token.get("userinfo")
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    user = models.User.get_by_email(db, email=user_data.get("email"))
    _check_active_user_exists(user)

    response = _generate_token_response(user.id)
    return response
