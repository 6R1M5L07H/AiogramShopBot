"""
FastAPI router for Telegram Mini App - PGP address input.

Serves HTML template with embedded PGP public key for client-side encryption.
"""

import base64
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

import config
from enums.bot_entity import BotEntity
from exceptions.shipping import PGPKeyNotConfiguredException
from utils.localizator import Localizator

# Initialize Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

mini_app_router = APIRouter(prefix="/webapp", tags=["miniapp"])


def load_pgp_public_key() -> str:
    """
    Load and decode PGP public key from config.

    Returns:
        str: ASCII-armored PGP public key

    Raises:
        PGPKeyNotConfiguredException: If PGP_PUBLIC_KEY_BASE64 not configured
    """
    if not config.PGP_PUBLIC_KEY_BASE64:
        raise PGPKeyNotConfiguredException()

    try:
        decoded = base64.b64decode(config.PGP_PUBLIC_KEY_BASE64).decode('utf-8')
        return decoded
    except Exception as e:
        logging.error(f"Failed to decode PGP public key: {e}")
        raise PGPKeyNotConfiguredException()


@mini_app_router.get("/pgp-address-input", response_class=HTMLResponse)
async def pgp_address_input(
    request: Request,
    order_id: int = Query(..., description="Order ID for address encryption"),
    lang: str = Query("de", description="Language code (de/en)")
):
    """
    Serve Telegram Mini App for encrypted shipping address input.

    Args:
        request: FastAPI request object
        order_id: Order ID to associate with encrypted address
        lang: Language code for localization (de or en)

    Returns:
        HTMLResponse: Rendered HTML template with embedded PGP key

    Raises:
        HTTPException: 500 if PGP key not configured
    """
    try:
        pgp_public_key = load_pgp_public_key()
    except PGPKeyNotConfiguredException as e:
        logging.error(f"PGP key not configured for Mini App: {e}")
        raise HTTPException(status_code=500, detail="PGP encryption not available")

    # Load localized strings using request-scoped language
    # FIXED: Pass lang parameter explicitly instead of mutating global state (race condition)
    page_title = Localizator.get_text(BotEntity.USER, "pgp_webapp_title", lang=lang)
    description = Localizator.get_text(BotEntity.USER, "pgp_webapp_description", lang=lang)
    security_title = Localizator.get_text(BotEntity.USER, "pgp_webapp_security_title", lang=lang)
    security_text = Localizator.get_text(BotEntity.USER, "pgp_webapp_security_text", lang=lang)
    input_label = Localizator.get_text(BotEntity.USER, "pgp_webapp_input_label", lang=lang)
    input_placeholder = Localizator.get_text(BotEntity.USER, "pgp_webapp_input_placeholder", lang=lang)
    main_button_text = Localizator.get_text(BotEntity.USER, "pgp_webapp_main_button", lang=lang)
    error_title = Localizator.get_text(BotEntity.USER, "pgp_webapp_error_title", lang=lang)
    error_empty_address = Localizator.get_text(BotEntity.USER, "pgp_webapp_error_empty", lang=lang)
    error_encryption = Localizator.get_text(BotEntity.USER, "pgp_webapp_error_encryption", lang=lang)
    status_encrypting = Localizator.get_text(BotEntity.USER, "pgp_webapp_status_encrypting", lang=lang)
    status_sending = Localizator.get_text(BotEntity.USER, "pgp_webapp_status_sending", lang=lang)

    # Render template with all variables
    return templates.TemplateResponse(
        "pgp_address_input.html",
        {
            "request": request,
            "lang": lang,
            "order_id": order_id,
            "pgp_public_key": pgp_public_key,
            "page_title": page_title,
            "description": description,
            "security_title": security_title,
            "security_text": security_text,
            "input_label": input_label,
            "input_placeholder": input_placeholder,
            "main_button_text": main_button_text,
            "error_title": error_title,
            "error_empty_address": error_empty_address,
            "error_encryption": error_encryption,
            "status_encrypting": status_encrypting,
            "status_sending": status_sending,
        }
    )