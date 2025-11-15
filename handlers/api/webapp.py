"""
FastAPI handlers for Telegram Mini Apps (WebApp)

Serves PGP encryption Mini App with backend template rendering.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import config
from exceptions.shipping import PGPKeyNotConfiguredException
from utils.localizator import Localizator
from enums.bot_entity import BotEntity


logger = logging.getLogger(__name__)

webapp_router = APIRouter(prefix="/webapp", tags=["webapp"])

# Static directory path
STATIC_DIR = Path(__file__).parent.parent.parent / "static" / "webapp"
TEMPLATE_PATH = STATIC_DIR / "shipping-encrypt-template.html"


@webapp_router.get("/shipping-encrypt-{lang}.html", response_class=HTMLResponse)
async def shipping_encrypt_miniapp(lang: str = "de"):
    """
    Serve PGP shipping address encryption Mini App with localized strings.

    Backend renders template with:
    - Localized UI strings
    - PGP public key (embedded in HTML)

    Args:
        lang: Language code ('de' or 'en')

    Returns:
        Rendered HTML with embedded PGP key and localized strings

    Raises:
        HTTPException 404: If language not supported
        HTTPException 500: If PGP key not configured
    """

    # Validate language
    if lang not in ["de", "en"]:
        raise HTTPException(status_code=404, detail=f"Language '{lang}' not supported")

    # Load PGP public key
    try:
        pgp_public_key = config.load_pgp_public_key()
    except PGPKeyNotConfiguredException as e:
        logger.error(f"PGP key not configured: {e}")
        raise HTTPException(
            status_code=500,
            detail="PGP encryption not available. Contact administrator."
        )

    # Load template
    if not TEMPLATE_PATH.exists():
        logger.error(f"Template not found: {TEMPLATE_PATH}")
        raise HTTPException(status_code=500, detail="Mini App template not found")

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Render template with localized strings
    rendered = template.replace("{{lang}}", lang)

    # Page metadata
    rendered = rendered.replace("{{page_title}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_page_title", lang))

    # Header
    rendered = rendered.replace("{{header_title}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_header_title", lang))
    rendered = rendered.replace("{{header_subtitle}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_header_subtitle", lang))

    # Info box
    rendered = rendered.replace("{{info_text}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_info_text", lang))

    # Form
    rendered = rendered.replace("{{label_address}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_label_address", lang))
    rendered = rendered.replace("{{placeholder_address}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_placeholder_address", lang))
    rendered = rendered.replace("{{hint_text}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_hint_text", lang))

    # Buttons
    rendered = rendered.replace("{{btn_encrypt}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_btn_encrypt", lang))
    rendered = rendered.replace("{{btn_cancel}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_btn_cancel", lang))

    # Footer
    rendered = rendered.replace("{{footer_text}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_footer_text", lang))

    # JavaScript strings
    rendered = rendered.replace("{{js_encrypting}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_js_encrypting", lang))
    rendered = rendered.replace("{{js_error_empty}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_js_error_empty", lang))
    rendered = rendered.replace("{{js_error_encryption}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_js_error_encryption", lang))
    rendered = rendered.replace("{{js_success}}",
        Localizator.get_text_with_lang(BotEntity.USER, "webapp_js_success", lang))

    # Embed PGP public key (escaped for JavaScript string)
    pgp_key_escaped = pgp_public_key.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    rendered = rendered.replace("{{pgp_public_key}}", pgp_key_escaped)

    return HTMLResponse(content=rendered)


@webapp_router.get("/webapp.css")
async def serve_css():
    """Serve Mini App CSS file."""
    css_path = STATIC_DIR / "webapp.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS file not found")
    return FileResponse(css_path, media_type="text/css")


@webapp_router.get("/encrypt.js")
async def serve_js():
    """Serve Mini App JavaScript file."""
    js_path = STATIC_DIR / "encrypt.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript file not found")
    return FileResponse(js_path, media_type="application/javascript")


@webapp_router.get("/openpgp.min.js")
async def serve_openpgp():
    """Serve OpenPGP.js library."""
    openpgp_path = STATIC_DIR / "openpgp.min.js"
    if not openpgp_path.exists():
        logger.error("OpenPGP.js not found. Download it first: curl -o static/webapp/openpgp.min.js https://unpkg.com/openpgp@5.11.0/dist/openpgp.min.js")
        raise HTTPException(
            status_code=404,
            detail="OpenPGP.js not found. See logs for download instructions."
        )
    return FileResponse(openpgp_path, media_type="application/javascript")
