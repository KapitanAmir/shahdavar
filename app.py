from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    jsonify,
)

from pathlib import Path

from werkzeug.utils import secure_filename

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

import os
import random
import re
import sqlite3
import secrets
import json
from html.parser import HTMLParser
import html as html_lib
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone, timedelta


# ============================================================
# LOCAL ENVIRONMENT LOADER
# ============================================================
# Flask/Python does not automatically read .env. Load the local
# provider configuration before importing the Shahdyar service.
def _load_local_env():
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as error:
        print(f"[ENV] Could not load .env: {error}")


_load_local_env()


from database import (
    init_db,

    get_site_settings,
    update_site_setting,

    get_products,
    get_product,
    add_product,
    update_product,
    delete_product,
    delete_product_image,

    get_categories,
    add_category,
    delete_category,
    update_category_cover,

    get_covers,
    add_cover,
    update_cover,
    delete_cover,

    get_logo,
    set_logo,
    delete_logo,

    get_user_by_phone,
    get_user_by_email,
    get_user,
    create_user,
    update_user,
    update_user_avatar,
    update_user_password,
    get_user_by_username,
    is_username_available,

    create_review,
    get_all_reviews,
    get_pending_reviews_count,
    set_review_status,
    set_review_reply,
    delete_review,

    get_or_create_support_conversation,
    get_support_conversations,
    get_support_conversation,
    get_support_messages,
    add_support_message,
    mark_support_messages_read,
    get_unread_support_count,
    get_product_reviews,
    get_user_count,
    get_users,
    get_cart,
    upsert_cart_item,
    update_cart_quantity,
    remove_cart_item,
    clear_cart,
    create_order_from_cart,
    get_user_orders,
    get_order_by_number,
    get_order_by_id,
    get_all_orders,
    update_order_status,
    get_or_create_recovery_conversation,
    get_recovery_conversations,
    get_recovery_messages,
    add_recovery_message,
    mark_recovery_read,
    get_unread_recovery_count,
    delete_recovery_conversation,
    get_recovery_conversation,
    get_review,
    update_support_message,
    delete_support_message,
    update_support_message_as_owner,
    delete_support_message_as_owner,
    set_support_message_meta,
    pin_support_message,
    get_profile_categories,
    create_profile_category,
    get_profile_category,
    create_profile,
    update_profile,
    delete_profile,
    get_profiles,
    get_profile,
    get_profile_by_slug,
    create_knowledge_article,
    update_knowledge_article,
    delete_knowledge_article,
    get_knowledge_articles,
    get_knowledge_article,
    get_knowledge_article_by_slug,

    # ========================================================
    # CONTACT SYSTEM
    # ========================================================
    get_contact_methods,
    get_contact_method,
    create_contact_method,
    update_contact_method,
    delete_contact_method,
    toggle_contact_method,
    move_contact_method,
    get_banners,
    add_banner,
    update_banner,
    delete_banner,
    toggle_banner,
    move_banner,
)


# ============================================================
# SHAH DYAR AI SERVICE
# ============================================================

from services.shahdyar_service import (
    create_chat_session,
    get_chat_session,
    delete_chat_session,
    can_send_message,
    get_messages,
    get_chat_status,
    generate_ai_response,
    get_provider_status,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

IMAGES_DIR = BASE_DIR / "images"
CSS_DIR = BASE_DIR / "css"
JS_DIR = BASE_DIR / "js"
UPLOADS_DIR = BASE_DIR / "uploads"

PRODUCTS_DIR = UPLOADS_DIR / "products"
COVERS_DIR = UPLOADS_DIR / "covers"
LOGO_DIR = UPLOADS_DIR / "logo"
BANNERS_DIR = UPLOADS_DIR / "banners"

PROFILES_DIR = UPLOADS_DIR / "profiles"
FEMALE_PROFILES_DIR = PROFILES_DIR / "female"
MALE_PROFILES_DIR = PROFILES_DIR / "male"

CONTACT_ICONS_DIR = UPLOADS_DIR / "contact_icons"
ABOUT_IMAGES_DIR = UPLOADS_DIR / "about"
SUPPORT_MEDIA_DIR = UPLOADS_DIR / "support"
SUPPORT_BRANDING_DIR = UPLOADS_DIR / "support_branding"
KNOWLEDGE_IMAGES_DIR = UPLOADS_DIR / "knowledge"
PROFILE_IMAGES_DIR = UPLOADS_DIR / "profile_knowledge"


for folder in (
    UPLOADS_DIR,
    PRODUCTS_DIR,
    COVERS_DIR,
    LOGO_DIR,
    BANNERS_DIR,
    PROFILES_DIR,
    FEMALE_PROFILES_DIR,
    MALE_PROFILES_DIR,
    CONTACT_ICONS_DIR,
    ABOUT_IMAGES_DIR,
    SUPPORT_MEDIA_DIR,
    SUPPORT_BRANDING_DIR,
    KNOWLEDGE_IMAGES_DIR,
    PROFILE_IMAGES_DIR,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder="templates",
)

def _get_secret_key():
    configured = os.getenv("FLASK_SECRET_KEY", "").strip()
    if configured:
        return configured
    secret_file = BASE_DIR / ".flask_secret_key"
    try:
        if secret_file.exists():
            value = secret_file.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_urlsafe(64)
        secret_file.write_text(value, encoding="utf-8")
        return value
    except OSError:
        return secrets.token_urlsafe(64)


app.secret_key = _get_secret_key()


# ============================================================
# SESSION
# ============================================================

app.config["PERMANENT_SESSION_LIFETIME"] = (
    60 * 60 * 24 * 365
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "1").strip().lower() in {"1", "true", "yes", "on"}
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

app.config["MAX_CONTENT_LENGTH"] = (
    120 * 1024 * 1024
)
app.config["SITE_PUBLIC_URL"] = os.getenv("SITE_PUBLIC_URL", "http://127.0.0.1:5000").rstrip("/")
app.config["GOOGLE_SITE_VERIFICATION"] = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()


# ============================================================
# OWNER
# ============================================================

OWNER_PHONES = {"09034296480", "09169740802", "09338940802"}
OWNER_PHONE = "09034296480"


# ============================================================
# DATABASE
# ============================================================

init_db()

# ============================================================
# FINAL 2026 SITE-BUILDER / NOTIFICATION MIGRATIONS
# ============================================================
def _ensure_final_schema():
    """Add final no-code site-builder settings and public profiles."""
    conn = sqlite3.connect(str(BASE_DIR / "honeyshop.db"))
    try:
        cur = conn.cursor()
        existing = {row[1] for row in cur.execute("PRAGMA table_info(site_settings)").fetchall()}
        migrations = {
            "home_layout": "TEXT DEFAULT ''",
            "footer_text": "TEXT DEFAULT ''",
            "footer_links_json": "TEXT DEFAULT '[]'",
            "order_notify_mode": "TEXT DEFAULT 'support'",
            "order_notify_telegram_bot_token": "TEXT DEFAULT ''",
            "order_notify_telegram_chat_id": "TEXT DEFAULT ''",
            "order_notify_webhook_url": "TEXT DEFAULT ''",
            "order_coordination_message": "TEXT DEFAULT 'سفارش شما ثبت شد. برای ادامه پرداخت لطفاً با فروشنده یا پشتیبانی شهدآور هماهنگ کنید.'",
            "support_profile_image": "TEXT DEFAULT ''",
            "support_background_image": "TEXT DEFAULT ''",
            "support_display_name": "TEXT DEFAULT 'پشتیبانی شهدآور'",
            "support_profile_text": "TEXT DEFAULT 'پاسخ‌گویی و هماهنگی سفارش‌های شهدآور'",
            "support_popup_text": "TEXT DEFAULT 'پشتیبانی شهدآور: سوالی دارید در خدمتم!'",
            "support_popup_color": "TEXT DEFAULT '#d9a62e'",
            "support_popup_enabled": "INTEGER DEFAULT 1",
        }
        for name, ddl in migrations.items():
            if name not in existing:
                cur.execute(f"ALTER TABLE site_settings ADD COLUMN {name} {ddl}")
        category_columns = {row[1] for row in cur.execute("PRAGMA table_info(categories)").fetchall()}
        if "cover_image" not in category_columns:
            cur.execute("ALTER TABLE categories ADD COLUMN cover_image TEXT DEFAULT ''")
        sm_columns = {row[1] for row in cur.execute("PRAGMA table_info(support_messages)").fetchall()}
        if "attachment_paths" not in sm_columns:
            cur.execute("ALTER TABLE support_messages ADD COLUMN attachment_paths TEXT DEFAULT '[]'")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payment_gateways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                driver TEXT NOT NULL DEFAULT 'manual',
                merchant_id TEXT DEFAULT '',
                api_key TEXT DEFAULT '',
                settings_json TEXT DEFAULT '{}',
                is_active INTEGER NOT NULL DEFAULT 0,
                is_default INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                bio_html TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                cover_image TEXT DEFAULT '',
                links_json TEXT DEFAULT '[]',
                is_published INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        conn.close()

_ensure_final_schema()


def _support_branding():
    """Always return a complete branding object so every template is safe."""
    site = get_site_settings() or default_site()
    return {
        "profile_image": site.get("support_profile_image") or "support-profile.png",
        "background_image": site.get("support_background_image") or "",
        "display_name": (site.get("support_display_name") or "پشتیبانی شهدآور").strip(),
        "profile_text": (site.get("support_profile_text") or site.get("support_text") or "پاسخ‌گویی و هماهنگی سفارش‌های شهدآور").strip(),
        "popup_text": (site.get("support_popup_text") or "پشتیبانی شهدآور: سوالی دارید در خدمتم!").strip(),
        "popup_color": site.get("support_popup_color") or "#d9a62e",
        "popup_enabled": bool(int(site.get("support_popup_enabled") or 1)),
        "status": "آنلاین",
    }


@app.before_request
def _csrf_protect():
    token = session.get("csrf_token") or _new_csrf_token()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if not supplied or not secrets.compare_digest(str(supplied), str(token)):
            return jsonify({"success": False, "message": "درخواست امنیتی نامعتبر است. صفحه را دوباره بارگذاری کنید."}), 400


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Keep owner mode usable while browsing the public storefront.
    if (session.get("is_owner") and request.path != "/owner" and not request.path.startswith("/owner/")
            and response.status_code == 200 and not response.is_streamed
            and response.content_type and response.content_type.startswith("text/html")):
        try:
            html = response.get_data(as_text=True)
            bar = """<div class="shd-owner-toolbar" dir="rtl" aria-label="ابزار مالکیت">
                <span>⚙️ حالت مالک</span>
                <a href="/owner">پنل مالکیت</a>
                <a href="/owner/site">ویرایش سایت</a>
                <a href="/owner/layout">چیدمان خانه</a>
                <a href="/owner/support-branding">پروفایل پشتیبانی</a>
            </div>
            <style>.shd-owner-toolbar{position:fixed;z-index:2147483000;right:14px;bottom:14px;display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:8px 10px;border:1px solid rgba(214,165,45,.35);border-radius:16px;background:rgba(28,24,18,.94);box-shadow:0 12px 35px rgba(0,0,0,.2);font:800 11px Tahoma;color:#f7e7b6;backdrop-filter:blur(12px)}.shd-owner-toolbar a{color:#211808!important;background:#efbf45;border-radius:10px;padding:7px 9px;text-decoration:none}.shd-owner-toolbar a:hover{filter:brightness(1.08)}@media(max-width:600px){.shd-owner-toolbar{left:8px;right:8px;bottom:8px;justify-content:center}.shd-owner-toolbar span{display:none}.shd-owner-toolbar a{font-size:9px;padding:7px 8px}}</style>"""
            if "</body>" in html:
                response.set_data(html.replace("</body>",bar+"</body>",1))
        except Exception:
            app.logger.exception("Owner storefront toolbar injection failed")
    # Public support launcher, welcome popup and decorative bees.
    if (not session.get("is_owner") and response.status_code == 200 and not response.is_streamed
            and response.content_type and response.content_type.startswith("text/html")
            and not request.path.startswith("/owner")):
        try:
            html=response.get_data(as_text=True); sb=_support_branding(); color=sb.get("popup_color") or "#d9a62e"
            profile=url_for("uploads",filename="support_branding/"+(sb.get("profile_image") or "support-profile.png"))
            popup=sb.get("popup_text") or "پشتیبانی شهدآور: سوالی دارید در خدمتم!"
            enabled="1" if sb.get("popup_enabled",True) else "0"
            widget=(f'<div id="shdSupportFloat" data-enabled="{enabled}" dir="rtl"><div class="shdSupportPopup"><img src="{profile}" alt="پشتیبانی"><div><strong>{popup}</strong><span>برای ارتباط با پشتیبانی اینجا کلیک کن</span></div><button id="shdSupportClose" type="button">×</button></div><a class="shdSupportFab" href="{url_for("support_page")}" aria-label="پشتیبانی">✦</a></div><div class="shdBees" aria-hidden="true"><i class="bee-a">🐝</i><i class="bee-b">🐝</i></div>'
                     '<style>#shdSupportFloat{position:fixed;left:16px;right:auto;bottom:16px;z-index:2147480000;font-family:Tahoma}.shdSupportPopup{display:flex;align-items:center;gap:9px;width:min(360px,calc(100vw - 30px));padding:9px 11px;background:#fffdf8;border:2px solid '+color+';border-radius:17px;box-shadow:0 15px 45px #3a290b25;margin-bottom:8px;cursor:pointer}.shdSupportPopup img{width:42px;height:42px;border-radius:50%;object-fit:cover;border:2px solid '+color+'}.shdSupportPopup div{flex:1;min-width:0}.shdSupportPopup strong{display:block;color:#3a2a10;font-size:11px;line-height:1.7}.shdSupportPopup span{display:block;color:#7c6a4e;font-size:9px;margin-top:2px}.shdSupportPopup button{border:0;background:none;font-size:19px;color:#73561c;cursor:pointer}.shdSupportFab{width:54px;height:54px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,'+color+',#f4d56a);border:2px solid #fff0ad;color:#30220a;text-decoration:none;font-size:22px;box-shadow:0 14px 35px #7d5b1e55}.shdBees{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:1}.shdBees i{position:absolute;font-style:normal;font-size:21px;opacity:.18;will-change:transform}.shdBees .bee-a{top:18%;left:-45px;animation:shdBeeA 18s linear infinite;transform:scaleX(-1)}.shdBees .bee-b{top:72%;left:-55px;animation:shdBeeB 23s linear infinite 3s;transform:scaleX(-1)}@keyframes shdBeeA{0%{transform:translate3d(-6vw,0,0) scaleX(-1)}18%{transform:translate3d(18vw,12vh,0) scaleX(-1)}42%{transform:translate3d(43vw,-9vh,0) scaleX(-1)}68%{transform:translate3d(72vw,16vh,0) scaleX(-1)}100%{transform:translate3d(112vw,-5vh,0) scaleX(-1)}}@keyframes shdBeeB{0%{transform:translate3d(-8vw,0,0) scaleX(-1)}22%{transform:translate3d(26vw,-17vh,0) scaleX(-1)}47%{transform:translate3d(52vw,8vh,0) scaleX(-1)}73%{transform:translate3d(79vw,-12vh,0) scaleX(-1)}100%{transform:translate3d(114vw,10vh,0) scaleX(-1)}}html[data-theme="dark"] .shdSupportPopup{background:#211d17}.shdSupportPopup strong{color:#3a2a10}@media(max-width:600px){#shdSupportFloat{left:9px;right:auto;bottom:9px}.shdSupportPopup{width:calc(100vw - 18px)}} </style>'
                     f'<script>(function(){{var w=document.getElementById("shdSupportFloat");if(!w)return;var p=w.querySelector(".shdSupportPopup"),c=document.getElementById("shdSupportClose");if(w.dataset.enabled!=="1"||localStorage.getItem("shd_support_popup_closed")==="1")p.style.display="none";c.onclick=function(e){{e.stopPropagation();p.style.display="none";localStorage.setItem("shd_support_popup_closed","1")}};p.onclick=function(e){{if(e.target!==c)location.href="{url_for("support_page")}"}}}})();</script>')
            if "</body>" in html: response.set_data(html.replace("</body>",widget+"</body>",1))
        except Exception:
            app.logger.exception("Support launcher injection failed")
    return response


# ============================================================
# FILES
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff",
    ".avif", ".heic", ".heif", ".ico", ".svg", ".jfif", ".jxl",
}

ALLOWED_CONTACT_ICON_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


# ============================================================
# USER COMPATIBILITY
# ============================================================

def get_user_by_id(user_id):

    if not user_id:
        return None

    try:

        user = get_user(
            user_id
        )

        if user:
            return user

    except Exception:
        pass

    try:

        conn = sqlite3.connect(
            BASE_DIR / "honeyshop.db"
        )

        conn.row_factory = sqlite3.Row

        try:

            row = conn.execute("""
                SELECT *
                FROM users
                WHERE id = ?
                LIMIT 1
            """, (
                user_id,
            )).fetchone()

            return (
                dict(row)
                if row
                else None
            )

        finally:

            conn.close()

    except Exception:

        return None


# ============================================================
# PRODUCT NORMALIZATION
# ============================================================

def _safe_int(
    value,
    default=0,
):

    if value is None:
        return default

    if isinstance(
        value,
        bool,
    ):
        return int(value)

    try:

        if isinstance(
            value,
            float,
        ):
            return int(value)

        value = str(
            value
        ).strip()

        value = value.translate(
            str.maketrans(
                "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                "01234567890123456789",
            )
        )

        value = value.replace(
            ",",
            "",
        )

        value = value.replace(
            "٬",
            "",
        )

        value = value.replace(
            " ",
            "",
        )

        value = value.replace(
            "تومان",
            "",
        )

        value = value.replace(
            "تومن",
            "",
        )

        if not value:
            return default

        return int(
            value
        )

    except (
        ValueError,
        TypeError,
    ):

        return default


def normalize_product(
    product
):

    if not product:
        return None

    product = dict(
        product
    )

    product["price"] = _safe_int(
        product.get("price"),
        0,
    )

    product["final_price"] = _safe_int(
        product.get("final_price"),
        0,
    )

    product["discount_percent"] = _safe_int(
        product.get("discount_percent"),
        0,
    )

    product["discount_days"] = _safe_int(
        product.get("discount_days"),
        0,
    )

    product["is_discount"] = bool(
        product.get(
            "is_discount",
            0,
        )
    )

    product["is_popular"] = bool(
        product.get(
            "is_popular",
            0,
        )
    )

    product["is_available"] = bool(
        product.get(
            "is_available",
            1,
        )
    )

    return product


def get_all_normalized_products():

    products = (
        get_products()
        or []
    )

    return [
        normalize_product(
            product
        )
        for product in products
        if product
    ]


def get_normalized_product(
    product_id,
):

    return normalize_product(
        get_product(
            product_id
        )
    )


# ============================================================
# HELPERS
# ============================================================

def normalize_phone(
    phone
):

    phone = (
        phone
        or ""
    ).strip()

    phone = phone.translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789",
        )
    )

    for char in (
        " ",
        "-",
        "(",
        ")",
    ):

        phone = phone.replace(
            char,
            "",
        )

    if phone.startswith(
        "+98"
    ):

        phone = (
            "0"
            + phone[3:]
        )

    elif phone.startswith(
        "0098"
    ):

        phone = (
            "0"
            + phone[4:]
        )

    return phone


def is_valid_phone(
    phone
):

    return (
        bool(phone)
        and len(phone) == 11
        and phone.startswith("09")
        and phone.isdigit()
    )


def get_random_avatar(
    gender
):

    if gender == "female":

        avatars = [
            f"female/female-{number:02d}.png"
            for number in range(
                1,
                11,
            )
        ]

    else:

        avatars = [
            f"male/male-{number:02d}.png"
            for number in range(
                1,
                11,
            )
        ]

    return random.choice(
        avatars
    )


def get_allowed_avatars(
    gender
):

    if gender not in {
        "male",
        "female",
    }:

        return []

    return [
        f"{gender}/{gender}-{number:02d}.png"
        for number in range(
            1,
            11,
        )
    ]


def _valid_image_bytes(file, extension):
    """Validate the actual file signature, not only its filename extension."""
    try:
        stream = file.stream
        position = stream.tell()
        header = stream.read(16)
        stream.seek(position)
    except Exception:
        return False
    signatures = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".gif": header.startswith(b"GIF87a") or header.startswith(b"GIF89a"),
        ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }
    return signatures.get(extension, False)


def save_uploaded_file(file, folder, allowed_extensions=None):
    if not file or not file.filename:
        return None
    filename = secure_filename(file.filename)
    if not filename:
        return None
    extension = Path(filename).suffix.lower()
    if allowed_extensions and extension not in allowed_extensions:
        return None
    try:
        stream = file.stream
        position = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(position)
    except Exception:
        return None
    if size <= 0 or size > 50 * 1024 * 1024:
        return None
    if extension in {".jpg", ".jpeg", ".png", ".webp", ".gif"} and not _valid_image_bytes(file, extension):
        return None
    # Create the target directory defensively and rewind before saving.
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        file.stream.seek(0)
    except Exception:
        return None
    unique_name = os.urandom(16).hex() + extension
    destination = Path(folder) / unique_name
    try:
        file.save(destination)
        if not destination.is_file() or destination.stat().st_size <= 0:
            destination.unlink(missing_ok=True)
            return None
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return unique_name


def delete_file_if_exists(
    folder,
    filename,
):

    if not filename:
        return

    filename = Path(
        filename
    ).name

    path = (
        folder
        / filename
    )

    try:

        if path.exists():
            path.unlink()

    except OSError:

        pass


USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{7,19}$")


def normalize_username(value):
    return (value or "").strip()


def is_valid_username(value):
    return bool(USERNAME_RE.fullmatch(normalize_username(value)))


class _SafeHTMLParser(HTMLParser):
    ALLOWED_TAGS = {
        "p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
        "strong", "em", "u", "s", "strike", "blockquote", "div", "span", "a", "img", "hr"
    }
    VOID_TAGS = {"br", "hr", "img"}
    ALLOWED_STYLES = {"color", "background-color", "text-align", "width", "height", "font-size"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    @staticmethod
    def _safe_url(value, image=False):
        value = (value or "").strip()
        parsed = urlparse(value)
        if image:
            if value.startswith(("/uploads/", "/images/")):
                return value
            return ""
        if parsed.scheme in {"http", "https", "mailto", "tel"}:
            return value
        if value.startswith("/") and not value.startswith("//"):
            return value
        return ""

    @staticmethod
    def _safe_style(value):
        clean = []
        for chunk in (value or "").split(";"):
            if ":" not in chunk:
                continue
            name, val = chunk.split(":", 1)
            name = name.strip().lower()
            val = val.strip()
            if name not in _SafeHTMLParser.ALLOWED_STYLES:
                continue
            if any(token in val.lower() for token in ("expression", "javascript:", "url(", "@import")):
                continue
            if name in {"width", "height", "font-size"} and not re.fullmatch(r"\d{1,4}(?:\.\d+)?(?:%|px|em|rem)?", val):
                continue
            if name == "text-align" and val not in {"left", "right", "center", "justify"}:
                continue
            if name in {"color", "background-color"} and not re.fullmatch(r"(?:#[0-9a-fA-F]{3,8}|[a-zA-Z]+|rgba?\([^)]*\)|hsla?\([^)]*\))", val):
                continue
            clean.append(f"{name}:{val}")
        return ";".join(clean)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self.ALLOWED_TAGS:
            return
        safe = []
        for name, value in attrs:
            name = name.lower()
            if name.startswith("on") or name in {"srcdoc", "formaction"}:
                continue
            if name == "style":
                value = self._safe_style(value)
                if value:
                    safe.append((name, value))
                continue
            if tag == "a" and name == "href":
                value = self._safe_url(value)
                if value:
                    safe.append((name, value))
                continue
            if tag == "img" and name == "src":
                value = self._safe_url(value, image=True)
                if value:
                    safe.append((name, value))
                continue
            if name in {"alt", "title", "target", "rel"}:
                safe.append((name, value or ""))
        if tag == "a":
            safe.append(("rel", "noopener noreferrer"))
            safe.append(("target", "_blank"))
        if tag == "img" and not any(k == "alt" for k, _ in safe):
            safe.append(("alt", "تصویر"))
        attrs_text = "".join(f' {k}="{html_lib.escape(str(v), quote=True)}"' for k, v in safe)
        self.parts.append(f"<{tag}{attrs_text}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.ALLOWED_TAGS and tag not in self.VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html_lib.escape(data))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")


def sanitize_rich_html(value):
    parser = _SafeHTMLParser()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts).strip()


def _new_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def is_owner_phone(phone):
    return normalize_phone(phone) in {normalize_phone(item) for item in OWNER_PHONES}


def _bind_owner_customer_session():
    """Keep the owner authenticated as a normal storefront user while owner mode is active."""
    if not session.get("is_owner", False):
        return None
    phone = normalize_phone(session.get("phone", ""))
    if not phone or not is_owner_phone(phone):
        return None
    try:
        user = get_user_by_phone(phone)
    except Exception:
        user = None
    if user and user.get("id"):
        session["user_id"] = user["id"]
    return user


def owner_required():

    _bind_owner_customer_session()
    if not session.get("is_owner", False) or not is_owner_phone(session.get("phone", "")):

        flash(
            "برای دسترسی به پنل مالکیت ابتدا وارد حساب مالک شوید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )

    return None


def parse_price(
    value
):

    return _safe_int(
        value,
        0,
    )


def parse_int(
    value,
    default=0,
):

    return _safe_int(
        value,
        default,
    )


def get_or_create_category_id(
    category_name
):

    name = (
        category_name
        or ""
    ).strip()

    if not name:
        return None

    normalized_name = (
        " ".join(
            name.split()
        ).casefold()
    )

    categories = (
        get_categories()
        or []
    )

    for category in categories:

        existing = (
            category.get(
                "name"
            )
            or ""
        ).strip()

        normalized_existing = (
            " ".join(
                existing.split()
            ).casefold()
        )

        if (
            normalized_existing
            == normalized_name
        ):

            return category.get(
                "id"
            )

    add_category(
        name
    )

    categories = (
        get_categories()
        or []
    )

    for category in categories:

        existing = (
            category.get(
                "name"
            )
            or ""
        ).strip()

        normalized_existing = (
            " ".join(
                existing.split()
            ).casefold()
        )

        if (
            normalized_existing
            == normalized_name
        ):

            return category.get(
                "id"
            )

    return None


def get_product_type(
    product
):

    if product.get(
        "is_discount"
    ):

        return "discount"

    if product.get(
        "is_popular"
    ):

        return "popular"

    return "normal"


def default_site():

    return {
        "site_name":
            "عسل شهدآور",

        "site_tagline":
            "طعم واقعی طبیعت",

        "welcome_text":
            (
                "🐝 سلام دوست عزیز؛ "
                "به بهشت عسل شهدآور خوش اومدی! 🍯"
            ),

        "about_text":
            "",

        "about_title":
            "درباره شهدآور",

        "about_image":
            "",

        "about_link":
            "",

        "support_text":
            "",

        "contact_text":
            (
                "برای خرید، دریافت اطلاعات محصولات "
                "یا ارتباط با شهدآور از راه‌های ارتباطی "
                "زیر با ما در تماس باشید."
            ),

        "contact_title":
            "تماس با شهدآور",

        "contact_button_text":
            "تماس با ما",

        "background_color":
            "#fffdf8",
    }


def default_covers():

    return [
        {
            "id": 1,
            "filename": "hero-1.jpg",
            "duration": 5,
        },
        {
            "id": 2,
            "filename": "hero-2.jpg",
            "duration": 5,
        },
        {
            "id": 3,
            "filename": "hero-3.jpg",
            "duration": 5,
        },
        {
            "id": 4,
            "filename": "hero-4.jpg",
            "duration": 5,
        },
        {
            "id": 5,
            "filename": "hero-5.jpg",
            "duration": 5,
        },
        {
            "id": 6,
            "filename": "hero-6.jpg",
            "duration": 5,
        },
    ]


# ============================================================
# CONTACT HELPERS
# ============================================================

CONTACT_PLATFORM_ICONS = {
    "telegram":"✈️", "rubika":"🟣", "eitaa":"🟢", "instagram":"📸",
    "whatsapp":"💬", "phone":"📞", "mobile":"📱", "email":"✉️",
    "website":"🌐", "custom":"🔗"
}

def default_contact_icon(platform, icon_emoji=None):
    return (icon_emoji or "").strip() or CONTACT_PLATFORM_ICONS.get((platform or "custom").lower(), "🔗")


def normalize_contact_link(
    link
):
    link = (link or "").strip()
    if not link:
        return ""
    parsed = urlparse(link)
    if parsed.scheme.lower() in {"http", "https", "mailto", "tel"}:
        return link
    if link.startswith("/") and not link.startswith("//"):
        return link
    return ""


def normalize_contact_value(
    value
):

    value = (
        value
        or ""
    ).strip()

    return value


def normalize_contact_record(
    contact
):

    if not contact:
        return None

    contact = dict(contact)

    icon_filename = (
        contact.get("icon_filename")
        or contact.get("icon")
        or ""
    )

    icon_emoji = (
        contact.get("icon_emoji")
        or "📞"
    )

    contact["icon_filename"] = icon_filename
    contact["icon"] = icon_filename
    contact["icon_emoji"] = icon_emoji or CONTACT_PLATFORM_ICONS.get((contact.get("platform") or "custom").lower(), "🔗")

    contact["is_active"] = bool(
        contact.get(
            "is_active",
            1,
        )
    )

    contact["sort_order"] = _safe_int(
        contact.get(
            "sort_order",
            0,
        ),
        0,
    )

    return contact


def get_normalized_contact_methods(
    active_only=False
):

    try:

        methods = (
            get_contact_methods(
                active_only=active_only
            )
            or []
        )

    except TypeError:

        methods = (
            get_contact_methods()
            or []
        )

        if active_only:

            methods = [
                item
                for item in methods
                if bool(
                    item.get(
                        "is_active",
                        1,
                    )
                )
            ]

    return [
        normalize_contact_record(
            item
        )
        for item in methods
        if item
    ]


def create_contact_compat(
    title,
    value,
    link,
    icon_filename,
    icon_emoji,
    is_active,
    sort_order=None,
    platform="",
    icon_type="emoji",
    description="",
    button_text="ارتباط",
):

    """
    سازگاری با نسخه‌های مختلف database.py.
    بعضی نسخه‌های قبلی تابع create_contact_method
    را فقط با icon_filename داشتند و بعضی نسخه‌ها
    icon_emoji را نیز قبول می‌کنند.
    """

    try:

        return create_contact_method(

            title=title,

            value=value,

            link=link,

            icon_filename=icon_filename or "",

            icon_emoji=icon_emoji or "📞",
            icon_type=icon_type or "emoji",
            platform=platform or "",
            description=description or "",
            button_text=button_text or "ارتباط",
            sort_order=sort_order,

            is_active=is_active,

        )

    except TypeError as error:

        error_text = str(error)

        if "icon_emoji" not in error_text:

            raise

        return create_contact_method(

            title=title,

            value=value,

            link=link,

            icon_filename=icon_filename or "",
            sort_order=sort_order,

            is_active=is_active,

        )


def update_contact_compat(
    contact_id,
    title,
    value,
    link,
    icon_filename,
    icon_emoji,
    is_active,
    sort_order=None,
    icon_type="emoji",
    platform="",
    description="",
    button_text="ارتباط",
):
    """Compatibility wrapper for the current contact database API."""
    try:
        return update_contact_method(
            contact_id=contact_id,
            title=title,
            value=value,
            link=link,
            icon_filename=icon_filename or "",
            icon_emoji=icon_emoji or "📞",
            icon_type=icon_type or "emoji",
            platform=platform or "",
            description=description or "",
            button_text=button_text or "ارتباط",
            is_active=is_active,
            sort_order=sort_order,
        )
    except TypeError as error:
        if "icon_type" not in str(error) and "icon_emoji" not in str(error):
            raise
        return update_contact_method(
            contact_id=contact_id,
            title=title,
            value=value,
            link=link,
            icon_filename=icon_filename or "",
            is_active=is_active,
            sort_order=sort_order,
        )

# ============================================================
# SHAH DYAR AUTHENTICATION
# ============================================================

def shahdyar_authenticated():

    return bool(
        session.get("user_id")
        or session.get("is_owner")
    )


def shahdyar_auth_required():

    if not shahdyar_authenticated():

        return jsonify({

            "success":
                False,

            "message":
                (
                    "برای استفاده از شهدیار "
                    "ابتدا وارد حساب کاربری خود شوید."
                ),

            "redirect":
                url_for(
                    "account"
                ),

        }), 401

    return None


def get_shahdyar_user_id():

    return (
        session.get("user_id")
        or "owner"
    )


# ============================================================
# GLOBALS
# ============================================================

@app.context_processor
def inject_globals():

    _bind_owner_customer_session()
    current_user = None

    user_id = session.get(
        "user_id"
    )

    if user_id:

        current_user = get_user_by_id(
            user_id
        )

        if not current_user:

            session.pop(
                "user_id",
                None,
            )

            session.pop(
                "phone",
                None,
            )

            session.pop(
                "is_owner",
                None,
            )

    return {

        "is_owner":
            session.get(
                "is_owner",
                False,
            ),

        "owner_phone":
            session.get(
                "phone",
                "",
            ),

        "current_user":
            current_user,

        "logo":
            get_logo() or {"filename": "logo/logo.png"},

        "csrf_token": session.get("csrf_token") or _new_csrf_token(),
        "support_branding": _support_branding(),

    }


@app.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("account"))


@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        phone = normalize_phone(request.form.get("phone"))
        if not is_owner_phone(phone):
            flash("این شماره مالک نیست.", "error")
            return redirect(url_for("account"))
        session.clear(); session.permanent=True; session["phone"]=phone; session["is_owner"]=True
        owner_user = get_user_by_phone(phone)
        if owner_user and owner_user.get("id"):
            session["user_id"] = owner_user["id"]
        return redirect(url_for("owner_dashboard"))
    return redirect(url_for("account"))


# ============================================================
# STATIC FILES
# ============================================================

@app.route(
    "/css/<path:filename>"
)
def css_files(
    filename
):

    return send_from_directory(
        CSS_DIR,
        filename,
    )


@app.route(
    "/js/<path:filename>"
)
def js_files(
    filename
):

    return send_from_directory(
        JS_DIR,
        filename,
    )


@app.route(
    "/images/<path:filename>"
)
def images(
    filename
):

    return send_from_directory(
        IMAGES_DIR,
        filename,
    )


@app.route(
    "/uploads/<path:filename>"
)
def uploads(
    filename
):

    return send_from_directory(
        UPLOADS_DIR,
        filename,
    )


@app.route("/uploaded/<path:filename>")
def uploaded_file(filename):
    """Serve profile and other uploaded assets using their relative upload path."""
    return send_from_directory(UPLOADS_DIR, filename)


# ============================================================
# ERROR
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(
    error
):

    flash(
        "حجم فایل بیش از حد مجاز است. حداکثر ۱۰ مگابایت.",
        "error",
    )

    return redirect(
        request.referrer
        or url_for(
            "home"
        )
    )


# ============================================================
# FINAL SITE-BUILDER HELPERS
# ============================================================
DEFAULT_HOME_LAYOUT = [
    {"key":"hero","label":"کاور اصلی","enabled":True},
    {"key":"intro","label":"معرفی شهدآور و میانبرها","enabled":True},
    {"key":"categories","label":"دسته‌بندی محصولات","enabled":True},
    {"key":"discount","label":"محصولات تخفیف‌دار","enabled":True},
    {"key":"popular","label":"محبوب‌ها","enabled":True},
    {"key":"normal","label":"محصولات منتخب","enabled":True},
    {"key":"articles","label":"مقالات و دانستنی‌ها","enabled":True},
]

def _json_setting(key, fallback):
    try:
        raw = (get_site_settings() or {}).get(key) or ""
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback

def get_home_layout():
    value = _json_setting("home_layout", DEFAULT_HOME_LAYOUT)
    if not isinstance(value, list):
        return DEFAULT_HOME_LAYOUT
    known = {x["key"] for x in DEFAULT_HOME_LAYOUT}
    custom = {x.get("key"):x for x in get_home_custom_rows()}
    normalized=[]; seen=set()
    for item in value:
        if not isinstance(item,dict): continue
        key=item.get("key")
        if key in known and key not in seen:
            d=next(x.copy() for x in DEFAULT_HOME_LAYOUT if x["key"]==key); d["enabled"]=bool(item.get("enabled",True)); d["label"]=item.get("label") or d["label"]
            normalized.append(d); seen.add(key)
        elif key in custom and key not in seen:
            d=dict(custom[key]); d["enabled"]=bool(item.get("enabled",d.get("enabled",True))); normalized.append(d); seen.add(key)
    for item in DEFAULT_HOME_LAYOUT:
        if item["key"] not in seen: normalized.append(item.copy()); seen.add(item["key"])
    for row in get_home_custom_rows():
        if row["key"] not in seen: normalized.append(row); seen.add(row["key"])
    return normalized

def _get_setting(key, default=""):
    try:
        return (get_site_settings() or {}).get(key) or default
    except Exception:
        return default

def _save_json_setting(key, value):
    update_site_setting(key, json.dumps(value, ensure_ascii=False))

def get_home_custom_rows():
    rows = _json_setting("home_custom_rows", [])
    if not isinstance(rows, list): return []
    out=[]
    for row in rows:
        if not isinstance(row, dict) or not row.get("key"): continue
        row=dict(row); slides=row.get("slides") if isinstance(row.get("slides"),list) else []
        row["slides"]=[dict(x) for x in slides[:10] if isinstance(x,dict) and x.get("filename")]
        row["enabled"]=bool(row.get("enabled",True))
        row["size"]=row.get("size") if row.get("size") in {"xs","sm","md","lg","xl","full"} else "lg"
        row["duration"]=max(1,min(120,int(row.get("duration") or 5)))
        out.append(row)
    return out

def _save_home_custom_rows(rows): _save_json_setting("home_custom_rows", rows)

def get_footer_links():
    value=_json_setting("footer_links_json", [])
    return value if isinstance(value,list) else []

def get_public_profile_for_user(user_id):
    conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db")); conn.row_factory=sqlite3.Row
    try:
        row=conn.execute("SELECT * FROM public_profiles WHERE user_id=?",(user_id,)).fetchone()
        return dict(row) if row else None
    finally: conn.close()

def get_public_profile(username):
    conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db")); conn.row_factory=sqlite3.Row
    try:
        row=conn.execute("SELECT * FROM public_profiles WHERE username=? AND is_published=1",(username,)).fetchone()
        return dict(row) if row else None
    finally: conn.close()

def _slug_username(value):
    value=(value or "").strip().lower()
    value=re.sub(r"\s+","-",value)
    value=re.sub(r"[^a-z0-9_\-آ-ی]","",value)
    return value[:40]

def send_order_notification(order, items):
    """Send order to configured Telegram bot/webhook; always keep local support fallback."""
    site=get_site_settings() or {}
    lines=[
        "🧾 سفارش جدید شهدآور",
        f"شماره سفارش: {order.get('order_number','')}",
        f"👤 مشتری: {order.get('customer_name','')}",
        f"📱 تلفن: {order.get('customer_phone','')}",
        "",
    ]
    for item in items:
        lines.append(f"🍯 {item.get('title','')} × {item.get('quantity',1)} — {int(item.get('line_total') or 0):,} تومان")
    lines += [
        "",
        f"💰 جمع محصولات: {int(order.get('subtotal') or 0):,} تومان",
        f"💳 مبلغ قابل پرداخت: {int(order.get('total_amount') or 0):,} تومان",
        "📌 پرداخت: هماهنگی با فروشنده / پشتیبانی",
    ]
    if order.get("customer_address"): lines.append(f"📍 آدرس: {order['customer_address']}")
    if order.get("notes"): lines.append(f"📝 یادداشت: {order['notes']}")
    message="\n".join(lines)
    sent=False; errors=[]
    mode=(site.get("order_notify_mode") or "support").strip()
    if mode in {"telegram","both"}:
        token=(site.get("order_notify_telegram_bot_token") or "").strip()
        chat_id=(site.get("order_notify_telegram_chat_id") or "").strip()
        if token and chat_id:
            try:
                payload=json.dumps({"chat_id":chat_id,"text":message,"disable_web_page_preview":True}).encode("utf-8")
                req=URLRequest(f"https://api.telegram.org/bot{token}/sendMessage",data=payload,headers={"Content-Type":"application/json"},method="POST")
                with urlopen(req,timeout=12) as resp:
                    data=json.loads(resp.read().decode("utf-8","ignore"))
                    sent=bool(data.get("ok"))
            except Exception as exc:
                errors.append(str(exc))
    webhook=(site.get("order_notify_webhook_url") or "").strip()
    if webhook and mode in {"webhook","both"}:
        try:
            payload=json.dumps({"event":"new_order","order":order,"items":items,"message":message},ensure_ascii=False).encode("utf-8")
            req=URLRequest(webhook,data=payload,headers={"Content-Type":"application/json"},method="POST")
            with urlopen(req,timeout=12) as resp: sent=200 <= resp.status < 300 or sent
        except Exception as exc:
            errors.append(str(exc))
    return sent, errors, message

def get_payment_gateways():
    conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db")); conn.row_factory=sqlite3.Row
    try:return [dict(r) for r in conn.execute("SELECT * FROM payment_gateways ORDER BY sort_order,id").fetchall()]
    finally:conn.close()

def save_payment_gateway(data, gateway_id=None):
    conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db"))
    try:
        if gateway_id:
            conn.execute("""UPDATE payment_gateways SET name=?,driver=?,merchant_id=?,api_key=?,settings_json=?,is_active=?,is_default=?,sort_order=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                         (data["name"],data["driver"],data["merchant_id"],data["api_key"],data["settings_json"],data["is_active"],data["is_default"],data["sort_order"],gateway_id))
        else:
            conn.execute("""INSERT INTO payment_gateways(name,driver,merchant_id,api_key,settings_json,is_active,is_default,sort_order) VALUES(?,?,?,?,?,?,?,?)""",
                         (data["name"],data["driver"],data["merchant_id"],data["api_key"],data["settings_json"],data["is_active"],data["is_default"],data["sort_order"]))
        if data["is_default"]:
            current=gateway_id or conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("UPDATE payment_gateways SET is_default=0 WHERE id<>?",(current,))
        conn.commit()
    finally:conn.close()

# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    site = (
        get_site_settings()
        or default_site()
    )

    products = (
        get_all_normalized_products()
    )

    visible_products = [
        product
        for product in products
        if product.get(
            "is_available",
            True,
        )
    ]

    discount_products = [
        product
        for product in visible_products
        if product.get(
            "is_discount"
        )
    ][:6]

    popular_products = [
        product
        for product in visible_products
        if product.get(
            "is_popular"
        )
    ][:6]

    normal_products = [
        product
        for product in visible_products
        if not product.get(
            "is_discount"
        )
        and not product.get(
            "is_popular"
        )
    ][:3]

    categories = (
        get_categories()
        or []
    )

    covers = (
        get_covers()
        or []
    )

    if not covers:
        covers = default_covers()

    logo = (
        get_logo()
        or {
            "filename":
                "logo/logo.png"
        }
    )

    articles = get_knowledge_articles(published_only=True)[:6]

    return render_template(
        "index.html",
        site=site,
        home_layout=get_home_layout(),
        articles=articles,
        products=products,
        normal_products=normal_products,
        discount_products=discount_products,
        popular_products=popular_products,
        categories=categories,
        covers=covers,
        logo=logo,
        custom_rows=get_home_custom_rows(),
    )


# ============================================================
# ACCOUNT PAGE
# ============================================================

@app.route(
    "/account",
    methods=[
        "GET",
        "POST",
    ],
)
def account():

    user_id = session.get(
        "user_id"
    )

    if user_id:

        user = get_user_by_id(
            user_id
        )

        if user:

            return render_template(
                "account.html",
                user=user,
                registration=False,
            )

        session.clear()


    # --------------------------------------------------------
    # POST LEGACY COMPATIBILITY
    # --------------------------------------------------------

    if request.method == "POST":

        phone = normalize_phone(
            request.form.get(
                "phone"
            )
        )

        if not is_valid_phone(
            phone
        ):

            flash(
                "شماره موبایل معتبر نیست.",
                "error",
            )

            return redirect(
                url_for(
                    "account"
                )
            )


        # ----------------------------------------------------
        # OWNER
        # ----------------------------------------------------

        if (
            is_owner_phone(phone)
        ):

            session.clear()

            session.permanent = True

            session["phone"] = phone

            session["is_owner"] = True
            owner_user = get_user_by_phone(phone)
            if owner_user and owner_user.get("id"):
                session["user_id"] = owner_user["id"]

            flash(
                "به پنل مالکیت شهدآور خوش آمدید.",
                "success",
            )

            return redirect(
                url_for(
                    "owner_dashboard"
                )
            )


        # ----------------------------------------------------
        # NORMAL USER
        # ----------------------------------------------------

        user = get_user_by_phone(
            phone
        )

        if user:

            session.clear()

            session.permanent = True

            session["user_id"] = user["id"]

            session["phone"] = user["phone"]

            session["is_owner"] = False

            return redirect(
                url_for(
                    "home"
                )
            )


        # ----------------------------------------------------
        # REGISTER
        # ----------------------------------------------------

        return render_template(
            "account.html",
            registration=True,
            phone=phone,
            user=None,
        )


    return render_template(
        "account.html",
        registration=False,
        user=None,
    )


# ============================================================
# REGISTER API
# ============================================================

@app.route(
    "/api/account/register",
    methods=["POST"],
)
def account_register():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    first_name = (
        data.get(
            "first_name"
        )
        or ""
    ).strip()

    last_name = (
        data.get(
            "last_name"
        )
        or ""
    ).strip()

    phone = normalize_phone(
        data.get(
            "phone"
        )
    )

    username = (
        data.get("username") or ""
    ).strip()
    email = (
        data.get(
            "email"
        )
        or ""
    ).strip().lower()

    province = (
        data.get(
            "province"
        )
        or ""
    ).strip()

    city = (
        data.get(
            "city"
        )
        or ""
    ).strip()

    gender = (
        data.get(
            "gender"
        )
        or ""
    ).strip().lower()

    password = (
        data.get(
            "password"
        )
        or ""
    )

    password_confirm = (
        data.get(
            "password_confirm"
        )
        or ""
    )

    terms = bool(
        data.get(
            "terms",
            False,
        )
    )


    # ========================================================
    # VALIDATION
    # ========================================================

    if not first_name:

        return jsonify({
            "message":
                "نام را وارد کنید.",
        }), 400


    if not last_name:

        return jsonify({
            "message":
                "نام خانوادگی را وارد کنید.",
        }), 400


    if not is_valid_phone(
        phone
    ):

        return jsonify({
            "message":
                "شماره موبایل معتبر نیست.",
        }), 400


    if not is_valid_username(username):
        return jsonify({"message": "نام کاربری باید ۸ تا ۲۰ کاراکتر، فقط انگلیسی/عدد/underscore باشد و با حرف شروع شود."}), 400

    if not is_username_available(username):
        return jsonify({"message": "این نام کاربری قبلاً استفاده شده است."}), 409


    if email:

        email_pattern = (
            r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        )

        if not re.match(
            email_pattern,
            email,
        ):

            return jsonify({
                "message":
                    "فرمت ایمیل صحیح نیست.",
            }), 400


    if not province:

        return jsonify({
            "message":
                "استان را انتخاب کنید.",
        }), 400


    if not city:

        return jsonify({
            "message":
                "شهر را وارد کنید.",
        }), 400


    if gender not in {
        "male",
        "female",
    }:

        return jsonify({
            "message":
                "جنسیت را انتخاب کنید.",
        }), 400


    if len(password) < 8:

        return jsonify({
            "message":
                "رمز عبور باید حداقل ۸ کاراکتر باشد.",
        }), 400


    if password != password_confirm:

        return jsonify({
            "message":
                "تکرار رمز عبور صحیح نیست.",
        }), 400


    if not terms:

        return jsonify({
            "message":
                (
                    "برای ساخت حساب باید "
                    "با قوانین سایت موافق باشید."
                ),
        }), 400


    # ========================================================
    # OWNER PHONE
    # ========================================================

    if (
        is_owner_phone(phone)
    ):

        return jsonify({
            "message":
                (
                    "این شماره برای حساب مالک "
                    "سایت رزرو شده است."
                ),
        }), 409


    # ========================================================
    # DUPLICATE PHONE
    # ========================================================

    existing_user = get_user_by_phone(
        phone
    )

    if existing_user:

        return jsonify({
            "message":
                (
                    "این شماره موبایل قبلاً "
                    "در سایت ثبت شده است."
                ),
        }), 409


    # ========================================================
    # DUPLICATE EMAIL
    # ========================================================

    if email:

        existing_email = get_user_by_email(
            email
        )

        if existing_email:

            return jsonify({
                "message":
                    (
                        "این ایمیل قبلاً "
                        "در سایت ثبت شده است."
                    ),
            }), 409


    # ========================================================
    # PASSWORD HASH
    # ========================================================

    password_hash = generate_password_hash(
        password
    )


    # ========================================================
    # RANDOM AVATAR
    # ========================================================

    avatar = get_random_avatar(
        gender
    )


    # ========================================================
    # CREATE USER
    # ========================================================

    try:

        user_id = create_user(

            first_name=first_name,

            last_name=last_name,

            phone=phone,

            email=email,

            province=province,

            city=city,

            gender=gender,

            password_hash=password_hash,

            avatar=avatar,

            terms_accepted=True,

            username=username,

        )

    except sqlite3.IntegrityError:

        return jsonify({
            "message":
                "این حساب قبلاً ثبت شده است.",
        }), 409

    except Exception:

        return jsonify({
            "message":
                (
                    "ساخت حساب انجام نشد. "
                    "لطفاً دوباره تلاش کنید."
                ),
        }), 500


    # ========================================================
    # LOGIN AFTER REGISTER
    # ========================================================

    session.clear()

    session.permanent = True

    session["user_id"] = user_id

    session["phone"] = phone

    session["is_owner"] = False


    return jsonify({

        "success":
            True,

        "message":
            (
                "حساب شما با موفقیت ساخته شد. "
                "خوش آمدید 🌿"
            ),

        "redirect":
            "/",

    }), 201


# ============================================================
# LOGIN API
# ============================================================

@app.route(
    "/api/account/login",
    methods=["POST"],
)
def account_login():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    phone = normalize_phone(
        data.get(
            "phone"
        )
    )

    password = (
        data.get(
            "password"
        )
        or ""
    )


    if not is_valid_phone(
        phone
    ):

        return jsonify({
            "message":
                "شماره موبایل معتبر نیست.",
        }), 400


    if not password:

        return jsonify({
            "message":
                "رمز عبور را وارد کنید.",
        }), 400


    # ========================================================
    # OWNER
    # ========================================================

    if (
        is_owner_phone(phone)
    ):

        session.clear()

        session.permanent = True

        session["phone"] = phone

        session["is_owner"] = True


        return jsonify({

            "success":
                True,

            "message":
                (
                    "به پنل مالکیت "
                    "شهدآور خوش آمدید."
                ),

            "redirect":
                "/owner",

        }), 200


    # ========================================================
    # NORMAL USER
    # ========================================================

    user = get_user_by_phone(
        phone
    )


    if not user:

        return jsonify({
            "message":
                (
                    "شماره موبایل یا "
                    "رمز عبور اشتباه است."
                ),
        }), 401


    stored_hash = (
        user.get(
            "password_hash"
        )
        or ""
    )


    if not stored_hash:

        return jsonify({
            "message":
                "این حساب هنوز رمز عبور ندارد.",
        }), 401


    try:

        password_valid = (
            check_password_hash(
                stored_hash,
                password,
            )
        )

    except Exception:

        password_valid = False


    if not password_valid:

        return jsonify({
            "message":
                (
                    "شماره موبایل یا "
                    "رمز عبور اشتباه است."
                ),
        }), 401


    # ========================================================
    # SESSION
    # ========================================================

    session.clear()

    session.permanent = True

    session["user_id"] = user["id"]

    session["phone"] = user["phone"]

    session["is_owner"] = False


    first_name = (
        user.get(
            "first_name"
        )
        or ""
    ).strip()


    welcome_name = (
        first_name
        if first_name
        else "عزیز"
    )


    return jsonify({

        "success":
            True,

        "message":
            (
                f"خوش آمدید "
                f"{welcome_name} 🌿"
            ),

        "redirect":
            "/",

    }), 200


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/logout"
)
def logout():

    chat_id = session.get(
        "shahdyar_chat_id"
    )

    user_id = get_shahdyar_user_id()

    if chat_id:

        try:

            delete_chat_session(
                chat_id,
                user_id,
            )

        except Exception:

            pass

    session.clear()

    flash(
        "از حساب کاربری خارج شدید.",
        "success",
    )

    return redirect(
        url_for(
            "home"
        )
    )


@app.route(
    "/api/account/logout",
    methods=["POST"],
)
def account_logout():

    chat_id = session.get(
        "shahdyar_chat_id"
    )

    user_id = get_shahdyar_user_id()

    if chat_id:

        try:

            delete_chat_session(
                chat_id,
                user_id,
            )

        except Exception:

            pass

    session.clear()

    return jsonify({

        "success":
            True,

        "message":
            "با موفقیت از حساب خارج شدید.",

    })


# ============================================================
# UPDATE ACCOUNT
# ============================================================

@app.route(
    "/account/update",
    methods=["POST"],
)
def update_account():

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return redirect(
            url_for(
                "account"
            )
        )


    user = get_user_by_id(
        user_id
    )

    if not user:

        session.clear()

        return redirect(
            url_for(
                "account"
            )
        )


    first_name = (
        request.form.get(
            "first_name"
        )
        or ""
    ).strip()


    last_name = (
        request.form.get(
            "last_name"
        )
        or ""
    ).strip()


    username = (
        request.form.get("username") or ""
    ).strip()

    email = (
        request.form.get(
            "email"
        )
        or ""
    ).strip().lower()


    province = (
        request.form.get(
            "province"
        )
        or ""
    ).strip()


    city = (
        request.form.get(
            "city"
        )
        or ""
    ).strip()


    gender = (
        request.form.get(
            "gender"
        )
        or ""
    ).strip().lower()


    if not first_name:

        flash(
            "نام را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    if not last_name:

        flash(
            "نام خانوادگی را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    if not is_valid_username(username):
        flash("نام کاربری باید ۸ تا ۲۰ کاراکتر، فقط انگلیسی/عدد/underscore باشد و با حرف شروع شود.", "error")
        return redirect(url_for("account"))

    if not is_username_available(username, exclude_user_id=user_id):
        flash("این نام کاربری قبلاً استفاده شده است.", "error")
        return redirect(url_for("account"))


    if email:

        email_pattern = (
            r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        )

        if not re.match(
            email_pattern,
            email,
        ):

            flash(
                "فرمت ایمیل صحیح نیست.",
                "error",
            )

            return redirect(
                url_for(
                    "account"
                )
            )


        existing_email = get_user_by_email(
            email
        )


        if (
            existing_email
            and existing_email.get(
                "id"
            ) != user_id
        ):

            flash(
                "این ایمیل قبلاً در سایت ثبت شده است.",
                "error",
            )

            return redirect(
                url_for(
                    "account"
                )
            )


    if not province:

        flash(
            "استان را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    if not city:

        flash(
            "شهر را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    if gender not in {
        "male",
        "female",
    }:

        flash(
            "جنسیت را انتخاب کنید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    old_gender = (
        user.get(
            "gender"
        )
        or "male"
    )


    if gender != old_gender:

        new_avatar = get_random_avatar(
            gender
        )

        update_user_avatar(
            user_id,
            new_avatar,
        )


    try:

        update_user(

            user_id=user_id,

            first_name=first_name,

            last_name=last_name,

            phone=user["phone"],

            email=email,

            province=province,

            city=city,

            gender=gender,

            username=username,

        )

    except sqlite3.IntegrityError:

        flash(
            "ذخیره اطلاعات حساب انجام نشد.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )

    except Exception:

        flash(
            "خطایی هنگام ذخیره اطلاعات رخ داد.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    session["phone"] = user[
        "phone"
    ]

    session["is_owner"] = False


    flash(
        "اطلاعات حساب با موفقیت به‌روزرسانی شد.",
        "success",
    )


    return redirect(
        url_for(
            "account"
        )
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/account/password",
    methods=["POST"],
)
def change_password():

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return redirect(
            url_for(
                "account"
            )
        )


    user = get_user_by_id(
        user_id
    )

    if not user:

        session.clear()

        return redirect(
            url_for(
                "account"
            )
        )


    current_password = (
        request.form.get(
            "current_password"
        )
        or ""
    )


    password = (
        request.form.get(
            "password"
        )
        or ""
    )


    password_confirm = (
        request.form.get(
            "password_confirm"
        )
        or ""
    )


    stored_hash = (
        user.get(
            "password_hash"
        )
        or ""
    )


    if (
        current_password
        and stored_hash
    ):

        try:

            valid_current_password = (
                check_password_hash(
                    stored_hash,
                    current_password,
                )
            )

        except Exception:

            valid_current_password = False


        if not valid_current_password:

            flash(
                "رمز عبور فعلی صحیح نیست.",
                "error",
            )

            return redirect(
                url_for(
                    "account"
                )
            )


    if len(password) < 8:

        flash(
            "رمز عبور باید حداقل ۸ کاراکتر باشد.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    if password != password_confirm:

        flash(
            "تکرار رمز عبور صحیح نیست.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    password_hash = generate_password_hash(
        password
    )


    try:

        update_user_password(
            user_id,
            password_hash,
        )

    except Exception:

        flash(
            "تغییر رمز عبور انجام نشد.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    flash(
        "رمز عبور با موفقیت تغییر کرد.",
        "success",
    )


    return redirect(
        url_for(
            "account"
        )
    )


# ============================================================
# CHANGE AVATAR
# ============================================================

@app.route(
    "/account/avatar",
    methods=["POST"],
)
def change_avatar():

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return redirect(
            url_for(
                "account"
            )
        )


    user = get_user_by_id(
        user_id
    )


    if not user:

        session.clear()

        return redirect(
            url_for(
                "account"
            )
        )


    avatar = (
        request.form.get(
            "avatar"
        )
        or ""
    ).strip()


    gender = (
        user.get(
            "gender"
        )
        or "male"
    )


    allowed_avatars = get_allowed_avatars(
        gender
    )


    if avatar not in allowed_avatars:

        flash(
            "تصویر پروفایل نامعتبر است.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    update_user_avatar(
        user_id,
        avatar,
    )


    flash(
        "تصویر پروفایل با موفقیت تغییر کرد.",
        "success",
    )


    return redirect(
        url_for(
            "account"
        )
    )


# ============================================================
# OWNER DASHBOARD
# ============================================================

@app.route(
    "/owner"
)
def owner_dashboard():

    guard = owner_required()

    if guard:
        return guard


    products = (
        get_all_normalized_products()
    )


    categories = (
        get_categories()
        or []
    )


    covers = (
        get_covers()
        or []
    )


    banners = (
        get_banners()
        or []
    )


    logo = get_logo()


    return render_template(

        "owner_dashboard.html",

        products=products,

        categories=categories,

        covers=covers,

        banners=banners,

        logo=logo,
        pending_reviews_count=get_pending_reviews_count(),
        unread_support_count=get_unread_support_count(),
        user_count=get_user_count(),
        unread_recovery_count=get_unread_recovery_count(),
        profile_count=len(get_profiles()),
        knowledge_count=len(get_knowledge_articles()),

    )


# ============================================================
# ADD PRODUCT
# ============================================================

@app.route(
    "/owner/products/add",
    methods=[
        "GET",
        "POST",
    ],
)
def add_product_page():

    guard = owner_required()

    if guard:
        return guard


    categories = (
        get_categories()
        or []
    )


    if request.method == "POST":

        title = (
            request.form.get(
                "title"
            )
            or ""
        ).strip()


        price = parse_price(
            request.form.get(
                "price"
            )
        )


        description = (
            request.form.get(
                "description"
            )
            or ""
        ).strip()

        tags = (request.form.get("tags") or "").strip()[:500]
        weight = (request.form.get("weight") or "").strip()[:80]
        stock = max(0, parse_int(request.form.get("stock")))

        category_name = (
            request.form.get(
                "category_name"
            )
            or ""
        ).strip()


        product_type = (
            request.form.get(
                "product_type",
                "normal",
            )
            or "normal"
        ).strip().lower()


        if product_type not in {
            "normal",
            "discount",
            "popular",
        }:

            product_type = "normal"

        is_available = request.form.get("is_available") in {"1", "true", "on", "yes"}


        if not title:

            flash(
                "عنوان محصول را وارد کنید.",
                "error",
            )

            return redirect(
                url_for(
                    "add_product_page"
                )
            )


        if price <= 0:

            flash(
                "قیمت محصول باید بیشتر از صفر باشد.",
                "error",
            )

            return redirect(
                url_for(
                    "add_product_page"
                )
            )


        if not category_name:

            flash(
                "نام دسته محصول را وارد کنید.",
                "error",
            )

            return redirect(
                url_for(
                    "add_product_page"
                )
            )


        category_id = (
            get_or_create_category_id(
                category_name
            )
        )


        if not category_id:

            flash(
                "دسته‌بندی محصول ایجاد نشد.",
                "error",
            )

            return redirect(
                url_for(
                    "add_product_page"
                )
            )


        is_discount = (
            product_type
            == "discount"
        )


        is_popular = (
            product_type
            == "popular"
        )


        discount_percent = 0

        final_price = 0

        discount_days = 0


        if is_discount:

            discount_percent = max(

                1,

                min(

                    100,

                    parse_int(

                        request.form.get(
                            "discount_percent"
                        )

                    ),

                ),

            )


            final_price = parse_price(

                request.form.get(
                    "final_price"
                )

            )


            discount_days = max(

                1,

                min(

                    365,

                    parse_int(

                        request.form.get(
                            "discount_days"
                        )

                    ),

                ),

            )


            if final_price <= 0:

                flash(
                    "قیمت نهایی را وارد کنید.",
                    "error",
                )

                return redirect(
                    url_for(
                        "add_product_page"
                    )
                )


            if final_price >= price:

                flash(
                    "قیمت نهایی باید کمتر از قیمت اصلی باشد.",
                    "error",
                )

                return redirect(
                    url_for(
                        "add_product_page"
                    )
                )


        if is_discount:

            status = "discount"

        elif is_popular:

            status = "popular"

        else:

            status = "normal"


        image_1 = save_uploaded_file(

            request.files.get(
                "image_1"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        image_2 = save_uploaded_file(

            request.files.get(
                "image_2"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        image_3 = save_uploaded_file(

            request.files.get(
                "image_3"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )

        # A selected image must either be saved successfully or the owner is told
        # before the product is created. This prevents the old "preview worked but
        # the saved product had no image" failure mode.
        for field_name, saved_name in (("image_1", image_1), ("image_2", image_2), ("image_3", image_3)):
            selected = request.files.get(field_name)
            if selected and selected.filename and not saved_name:
                flash(f"تصویر {field_name[-1]} قابل ذخیره نبود؛ فرمت/حجم فایل را بررسی کنید.", "error")
                for candidate in (image_1, image_2, image_3):
                    if candidate: delete_file_if_exists(PRODUCTS_DIR, candidate)
                return redirect(url_for("add_product_page"))


        try:
            product_id = add_product(
                title=title, price=price, description=description, category_id=category_id,
                image_1=image_1, image_2=image_2, image_3=image_3, status=status,
                discount_percent=discount_percent, final_price=final_price, discount_days=discount_days,
                is_discount=is_discount, is_popular=is_popular, is_available=is_available,
                tags=tags, weight=weight, stock=stock,
            )
        except Exception:
            for candidate in (image_1, image_2, image_3):
                if candidate: delete_file_if_exists(PRODUCTS_DIR, candidate)
            app.logger.exception("Product creation failed")
            flash("ثبت محصول انجام نشد؛ اطلاعات واردشده یا ساختار پایگاه‌داده را بررسی کنید.", "error")
            return redirect(url_for("add_product_page"))

        if not product_id:
            for candidate in (image_1, image_2, image_3):
                if candidate: delete_file_if_exists(PRODUCTS_DIR, candidate)
            flash("ثبت محصول انجام نشد. لطفاً دوباره تلاش کنید.", "error")
            return redirect(url_for("add_product_page"))

        flash("محصول با موفقیت ثبت شد و اکنون در فروشگاه قابل مشاهده است.", "success")
        return redirect(url_for("owner_dashboard"))


    return render_template(

        "add_product.html",

        categories=categories,

    )


# ============================================================
# EDIT PRODUCT
# ============================================================

@app.route(
    "/owner/products/<int:product_id>/edit",
    methods=[
        "GET",
        "POST",
    ],
)
def edit_product_page(
    product_id
):

    guard = owner_required()

    if guard:
        return guard


    product = get_normalized_product(
        product_id
    )


    if not product:

        flash(
            "محصول پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "owner_dashboard"
            )
        )


    categories = (
        get_categories()
        or []
    )


    if request.method == "POST":

        title = (
            request.form.get(
                "title"
            )
            or ""
        ).strip()


        price = parse_price(
            request.form.get(
                "price"
            )
        )


        description = (
            request.form.get(
                "description"
            )
            or ""
        ).strip()

        tags = (request.form.get("tags") or "").strip()[:500]
        weight = (request.form.get("weight") or "").strip()[:80]
        stock = max(0, parse_int(request.form.get("stock")))

        category_name = (
            request.form.get(
                "category_name"
            )
            or ""
        ).strip()


        product_type = (
            request.form.get(
                "product_type",
                "normal",
            )
            or "normal"
        ).strip().lower()


        if product_type not in {
            "normal",
            "discount",
            "popular",
        }:

            product_type = "normal"

        is_available = request.form.get("is_available") in {"1", "true", "on", "yes"}


        if not title:

            flash(
                "عنوان محصول الزامی است.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_product_page",
                    product_id=product_id,
                )
            )


        if price <= 0:

            flash(
                "قیمت محصول باید بیشتر از صفر باشد.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_product_page",
                    product_id=product_id,
                )
            )


        if not category_name:

            flash(
                "نام دسته محصول الزامی است.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_product_page",
                    product_id=product_id,
                )
            )


        category_id = (
            get_or_create_category_id(
                category_name
            )
        )


        if not category_id:

            flash(
                "دسته‌بندی محصول ایجاد نشد.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_product_page",
                    product_id=product_id,
                )
            )


        is_discount = (
            product_type
            == "discount"
        )


        is_popular = (
            product_type
            == "popular"
        )


        discount_percent = 0

        final_price = 0

        discount_days = 0


        if is_discount:

            discount_percent = max(

                1,

                min(

                    100,

                    parse_int(

                        request.form.get(
                            "discount_percent"
                        )

                    ),

                ),

            )


            final_price = parse_price(

                request.form.get(
                    "final_price"
                )

            )


            discount_days = max(

                1,

                min(

                    365,

                    parse_int(

                        request.form.get(
                            "discount_days"
                        )

                    ),

                ),

            )


            if final_price <= 0:

                flash(
                    "قیمت نهایی را وارد کنید.",
                    "error",
                )

                return redirect(
                    url_for(
                        "edit_product_page",
                        product_id=product_id,
                    )
                )


            if final_price >= price:

                flash(
                    "قیمت نهایی باید کمتر از قیمت اصلی باشد.",
                    "error",
                )

                return redirect(
                    url_for(
                        "edit_product_page",
                        product_id=product_id,
                    )
                )


        if is_discount:

            status = "discount"

        elif is_popular:

            status = "popular"

        else:

            status = "normal"


        image_1 = (
            product.get(
                "image_1"
            )
            or ""
        )


        image_2 = (
            product.get(
                "image_2"
            )
            or ""
        )


        image_3 = (
            product.get(
                "image_3"
            )
            or ""
        )


        new_image_1 = save_uploaded_file(

            request.files.get(
                "image_1"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        new_image_2 = save_uploaded_file(

            request.files.get(
                "image_2"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        new_image_3 = save_uploaded_file(

            request.files.get(
                "image_3"
            ),

            PRODUCTS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        if new_image_1:

            delete_file_if_exists(
                PRODUCTS_DIR,
                image_1,
            )

            image_1 = new_image_1


        if new_image_2:

            delete_file_if_exists(
                PRODUCTS_DIR,
                image_2,
            )

            image_2 = new_image_2


        if new_image_3:

            delete_file_if_exists(
                PRODUCTS_DIR,
                image_3,
            )

            image_3 = new_image_3


        update_product(

            product_id=product_id,

            title=title,

            price=price,

            description=description,

            category_id=category_id,

            status=status,

            discount_percent=discount_percent,

            final_price=final_price,

            discount_days=discount_days,

            new_images=[
                image_1,
                image_2,
                image_3,
            ],
            tags=tags,
            weight=weight,
            stock=stock,

        )


        try:

            conn = sqlite3.connect(
                BASE_DIR / "honeyshop.db"
            )

            conn.execute("""
                UPDATE products
                SET
                    is_discount = ?,
                    is_popular = ?,
                    is_available = ?
                WHERE id = ?
            """, (
                1 if is_discount else 0,
                1 if is_popular else 0,
                1,
                product_id,
            ))

            conn.commit()
            conn.close()

        except sqlite3.Error:

            pass


        flash(
            "تغییرات محصول با موفقیت ذخیره شد.",
            "success",
        )


        return redirect(
            url_for(
                "owner_dashboard"
            )
        )


    return render_template(

        "edit_product.html",

        product=product,

        categories=categories,

        product_type=
            get_product_type(
                product
            ),

    )


# ============================================================
# DELETE PRODUCT IMAGE
# ============================================================

@app.route(
    "/owner/products/<int:product_id>/image/<int:image_number>/delete",
    methods=["POST"],
)
def delete_product_image_route(
    product_id,
    image_number,
):

    guard = owner_required()

    if guard:
        return guard


    if image_number not in (
        1,
        2,
        3,
    ):

        flash(
            "تصویر نامعتبر است.",
            "error",
        )

        return redirect(
            url_for(
                "edit_product_page",
                product_id=product_id,
            )
        )


    product = get_normalized_product(
        product_id
    )


    if not product:

        flash(
            "محصول پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "owner_dashboard"
            )
        )


    image_key = (
        f"image_{image_number}"
    )


    filename = product.get(
        image_key
    )


    delete_file_if_exists(
        PRODUCTS_DIR,
        filename,
    )


    delete_product_image(
        product_id,
        image_number,
    )


    flash(
        f"تصویر {image_number} با موفقیت حذف شد.",
        "success",
    )


    return redirect(
        url_for(
            "edit_product_page",
            product_id=product_id,
        )
    )


# ============================================================
# DELETE PRODUCT
# ============================================================

@app.route(
    "/owner/products/<int:product_id>/delete",
    methods=["POST"],
)
def delete_product_route(
    product_id
):

    guard = owner_required()

    if guard:
        return guard


    product = get_normalized_product(
        product_id
    )


    if not product:

        flash(
            "محصول پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "owner_dashboard"
            )
        )


    for image in (

        product.get(
            "image_1"
        ),

        product.get(
            "image_2"
        ),

        product.get(
            "image_3"
        ),

    ):

        delete_file_if_exists(
            PRODUCTS_DIR,
            image,
        )


    delete_product(
        product_id
    )


    flash(
        "محصول و تصاویر آن با موفقیت حذف شد.",
        "success",
    )


    return redirect(
        url_for(
            "owner_dashboard"
        )
    )


# ============================================================
# CATEGORIES
# ============================================================

@app.route(
    "/owner/categories",
    methods=[
        "GET",
        "POST",
    ],
)
def manage_categories():

    guard = owner_required()

    if guard:
        return guard


    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        category_id = request.form.get("category_id", type=int)
        cover = request.files.get("cover")
        if category_id and cover and cover.filename:
            filename = save_uploaded_file(cover, COVERS_DIR, ALLOWED_IMAGE_EXTENSIONS)
            if filename:
                current = next((c for c in (get_categories() or []) if int(c.get("id")) == category_id), None)
                update_category_cover(category_id, filename)
                if current and current.get("cover_image"):
                    delete_file_if_exists(COVERS_DIR, current.get("cover_image"))
                flash("کاور دسته با موفقیت ذخیره شد.", "success")
            else:
                flash("تصویر کاور قابل ذخیره نبود.", "error")
        elif name:
            add_category(name)
            flash("دسته‌بندی ایجاد شد.", "success")
        return redirect(url_for("manage_categories"))


    return render_template(

        "manage_categories.html",

        categories=
            get_categories()
            or [],

    )


@app.route(
    "/owner/categories/<int:category_id>/delete",
    methods=["POST"],
)
def delete_category_route(
    category_id
):

    guard = owner_required()

    if guard:
        return guard


    delete_category(
        category_id
    )


    flash(
        "دسته‌بندی حذف شد.",
        "success",
    )


    return redirect(
        url_for(
            "manage_categories"
        )
    )


# ============================================================
# COVERS
# ============================================================

@app.route(
    "/owner/covers",
    methods=[
        "GET",
        "POST",
    ],
)
def manage_covers():

    guard = owner_required()

    if guard:
        return guard


    if request.method == "POST":

        filename = save_uploaded_file(

            request.files.get(
                "cover"
            ),

            COVERS_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        if not filename:

            flash(
                "لطفاً یک تصویر معتبر انتخاب کنید.",
                "error",
            )

            return redirect(
                url_for(
                    "manage_covers"
                )
            )


        covers = (
            get_covers()
            or []
        )


        if len(covers) >= 10:

            delete_file_if_exists(

                COVERS_DIR,

                filename,

            )

            flash(
                "حداکثر ۱۰ کاور می‌توان داشت.",
                "error",
            )

            return redirect(
                url_for(
                    "manage_covers"
                )
            )


        duration = max(

            1,

            min(

                120,

                parse_int(

                    request.form.get(
                        "duration",
                        5,
                    ),

                    5,

                ),

            ),

        )


        add_cover(

            filename,

            duration,

        )


        flash(
            "کاور با موفقیت اضافه شد.",
            "success",
        )


        return redirect(
            url_for(
                "manage_covers"
            )
        )


    return render_template(

        "manage_covers.html",

        covers=
            get_covers()
            or [],

    )


@app.route(
    "/owner/covers/<int:cover_id>/update",
    methods=["POST"],
)
def update_cover_route(
    cover_id
):

    guard = owner_required()

    if guard:
        return guard


    covers = (
        get_covers()
        or []
    )


    current = next(

        (

            cover

            for cover
            in covers

            if cover.get(
                "id"
            )
            == cover_id

        ),

        None,

    )


    if not current:

        flash(
            "کاور پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_covers"
            )
        )


    duration = max(

        1,

        min(

            120,

            parse_int(

                request.form.get(

                    "duration",

                    current.get(
                        "duration",
                        5,
                    ),

                ),

                5,

            ),

        ),

    )


    new_file = save_uploaded_file(

        request.files.get(
            "cover"
        ),

        COVERS_DIR,

        ALLOWED_IMAGE_EXTENSIONS,

    )


    old_file = (
        current.get(
            "filename"
        )
    )


    filename = (
        new_file
        or old_file
    )


    update_cover(

        cover_id,

        filename=filename,

        duration=duration,

        sort_order=current.get("sort_order"),

    )


    if new_file:

        delete_file_if_exists(
            COVERS_DIR,
            old_file,
        )


    flash(
        "کاور با موفقیت به‌روزرسانی شد.",
        "success",
    )


    return redirect(
        url_for(
            "manage_covers"
        )
    )


@app.route(
    "/owner/covers/<int:cover_id>/delete",
    methods=["POST"],
)
def delete_cover_route(
    cover_id
):

    guard = owner_required()

    if guard:
        return guard


    cover = delete_cover(
        cover_id
    )


    if cover:

        delete_file_if_exists(

            COVERS_DIR,

            cover.get(
                "filename"
            ),

        )


        flash(
            "کاور با موفقیت حذف شد.",
            "success",
        )


    else:

        flash(
            "کاور پیدا نشد.",
            "error",
        )


    return redirect(
        url_for(
            "manage_covers"
        )
    )


@app.route("/owner/covers/<int:cover_id>/move/<direction>", methods=["POST"])
def move_cover_route(cover_id, direction):
    guard = owner_required()
    if guard: return guard
    if direction not in {"up", "down"}:
        flash("جهت جابه‌جایی نامعتبر است.", "error")
        return redirect(url_for("manage_covers"))
    covers = get_covers() or []
    index = next((i for i, c in enumerate(covers) if c.get("id") == cover_id), None)
    if index is None:
        flash("کاور پیدا نشد.", "error")
        return redirect(url_for("manage_covers"))
    neighbor_index = index - 1 if direction == "up" else index + 1
    if neighbor_index < 0 or neighbor_index >= len(covers):
        flash("این کاور در این جهت جای دیگری ندارد.", "info")
        return redirect(url_for("manage_covers"))
    a, b = covers[index], covers[neighbor_index]
    from database import update_cover as _update_cover
    _update_cover(a["id"], a["filename"], a.get("duration", 5), b.get("sort_order", neighbor_index))
    _update_cover(b["id"], b["filename"], b.get("duration", 5), a.get("sort_order", index))
    flash("ترتیب کاورها به‌روزرسانی شد.", "success")
    return redirect(url_for("manage_covers"))


# ============================================================
# LOGO
# ============================================================

@app.route(
    "/owner/logo",
    methods=[
        "GET",
        "POST",
    ],
)
def manage_logo():

    guard = owner_required()

    if guard:
        return guard


    if request.method == "POST":

        filename = save_uploaded_file(

            request.files.get(
                "logo"
            ),

            LOGO_DIR,

            ALLOWED_IMAGE_EXTENSIONS,

        )


        if not filename:

            flash(
                "لطفاً یک تصویر معتبر انتخاب کنید.",
                "error",
            )

            return redirect(
                url_for(
                    "manage_logo"
                )
            )


        old_logo = get_logo()


        set_logo(
            filename
        )


        if old_logo:

            delete_file_if_exists(

                LOGO_DIR,

                old_logo.get(
                    "filename"
                ),

            )


        flash(
            "لوگو با موفقیت تغییر کرد.",
            "success",
        )


        return redirect(
            url_for(
                "manage_logo"
            )
        )


    return render_template(

        "manage_logo.html",

        logo=get_logo(),

    )


@app.route(
    "/owner/logo/delete",
    methods=["POST"],
)
def delete_logo_route():

    guard = owner_required()

    if guard:
        return guard


    logo = delete_logo()


    if logo:

        delete_file_if_exists(

            LOGO_DIR,

            logo.get(
                "filename"
            ),

        )


        flash(
            "لوگو حذف شد.",
            "success",
        )


    return redirect(
        url_for(
            "manage_logo"
        )
    )


# ============================================================
# SITE
# ============================================================

@app.route(
    "/owner/site",
    methods=[
        "GET",
        "POST",
    ],
)
def manage_site():

    guard = owner_required()

    if guard:
        return guard


    if request.method == "POST":

        settings = {

            "site_name":
                (
                    request.form.get(
                        "site_name"
                    )
                    or ""
                ).strip(),

            "site_tagline":
                (
                    request.form.get(
                        "site_tagline"
                    )
                    or ""
                ).strip(),

            "welcome_text":
                (
                    request.form.get(
                        "welcome_text"
                    )
                    or ""
                ).strip(),

            "about_text":
                sanitize_rich_html(request.form.get("about_text") or ""),

            "about_title":
                (request.form.get("about_title") or "درباره شهدآور").strip(),

            "about_link":
                (request.form.get("about_link") or "").strip(),

            "support_text":
                (
                    request.form.get(
                        "support_text"
                    )
                    or ""
                ).strip(),

            "contact_text":
                (
                    request.form.get(
                        "contact_text"
                    )
                    or ""
                ).strip(),

            "contact_title":
                (
                    request.form.get(
                        "contact_title"
                    )
                    or "تماس با شهدآور"
                ).strip(),

            "contact_button_text":
                (
                    request.form.get(
                        "contact_button_text"
                    )
                    or "تماس با ما"
                ).strip(),

            "background_color":
                (
                    request.form.get(
                        "background_color"
                    )
                    or "#fffdf8"
                ).strip(),
            "footer_text": (request.form.get("footer_text") or "").strip(),
            "footer_links_json": (request.form.get("footer_links_json") or "[]").strip(),
            "order_notify_mode": (request.form.get("order_notify_mode") or "support").strip(),
            "order_notify_telegram_bot_token": (request.form.get("order_notify_telegram_bot_token") or "").strip(),
            "order_notify_telegram_chat_id": (request.form.get("order_notify_telegram_chat_id") or "").strip(),
            "order_notify_webhook_url": (request.form.get("order_notify_webhook_url") or "").strip(),
            "order_coordination_message": (request.form.get("order_coordination_message") or "").strip()[:500],

        }


        about_image = save_uploaded_file(request.files.get("about_image"), BANNERS_DIR, ALLOWED_IMAGE_EXTENSIONS)
        remove_about_image = request.form.get("remove_about_image") == "1"
        old_site = get_site_settings() or default_site()
        old_about_image = old_site.get("about_image") or ""
        if about_image:
            settings["about_image"] = about_image
        elif remove_about_image:
            settings["about_image"] = ""
        else:
            settings["about_image"] = old_about_image

        try:
            footer_links=json.loads(settings.get("footer_links_json") or "[]")
            if not isinstance(footer_links,list): raise ValueError
            footer_links=[{"title":str(x.get("title","")).strip()[:80],"url":str(x.get("url","")).strip()[:300]} for x in footer_links if isinstance(x,dict) and str(x.get("title","")).strip() and str(x.get("url","")).strip()]
            settings["footer_links_json"]=json.dumps(footer_links,ensure_ascii=False)
        except Exception:
            settings["footer_links_json"]=json.dumps([],ensure_ascii=False)

        for key, value in (
            settings.items()
        ):
            update_site_setting(key, value)

        if (about_image or remove_about_image) and old_about_image and old_about_image != settings.get("about_image"):
            delete_file_if_exists(BANNERS_DIR, old_about_image)


        flash(
            "تنظیمات سایت ذخیره شد.",
            "success",
        )


        return redirect(
            url_for(
                "manage_site"
            )
        )


    return render_template(

        "manage_site.html",

        site=(
            get_site_settings()
            or default_site()
        ),
        home_layout=get_home_layout(),
        payment_gateways=get_payment_gateways(),

    )


# ============================================================
# OWNER: VISUAL BUILDER / PAYMENT GATEWAYS
# ============================================================
@app.route("/owner/layout", methods=["GET","POST"])
def owner_layout():
    guard=owner_required()
    if guard:return guard
    layout=get_home_layout()
    if request.method=="POST":
        action=request.form.get("action",""); key=request.form.get("key","")
        if action=="add_custom":
            title=(request.form.get("title") or "ردیف جدید شهدآور").strip()[:100]
            subtitle=(request.form.get("subtitle") or "").strip()[:220]
            size=request.form.get("size") if request.form.get("size") in {"xs","sm","md","lg","xl","full"} else "lg"
            duration=max(1,min(120,request.form.get("duration",type=int) or 5)); files=request.files.getlist("slides")[:10]
            row_key="custom_"+secrets.token_hex(6); row_dir=UPLOADS_DIR/"home_rows"/row_key; row_dir.mkdir(parents=True,exist_ok=True); slides=[]
            for f in files:
                if f and f.filename:
                    fn=save_uploaded_file(f,row_dir,ALLOWED_IMAGE_EXTENSIONS)
                    if fn: slides.append({"filename":f"home_rows/{row_key}/{fn}","alt":title})
            if not slides: flash("حداقل یک تصویر برای ردیف سفارشی انتخاب کنید.","error")
            else:
                row={"key":row_key,"label":title,"title":title,"subtitle":subtitle,"enabled":True,"size":size,"duration":duration,"slides":slides}
                rows=get_home_custom_rows(); rows.append(row); _save_home_custom_rows(rows)
                pos=request.form.get("position",type=int); pos=len(layout) if pos is None else max(0,min(len(layout),pos)); layout.insert(pos,row); _save_json_setting("home_layout",layout)
                flash("ردیف سفارشی صفحه خانه ساخته شد.","success")
            return redirect(url_for("owner_layout"))
        if action=="delete_custom" and key.startswith("custom_"):
            _save_home_custom_rows([r for r in get_home_custom_rows() if r.get("key")!=key]); _save_json_setting("home_layout",[x for x in layout if x.get("key")!=key]); flash("ردیف سفارشی حذف شد.","success"); return redirect(url_for("owner_layout"))
        idx=next((i for i,x in enumerate(layout) if x["key"]==key),None)
        if idx is not None:
            if action=="toggle": layout[idx]["enabled"]=not layout[idx].get("enabled",True)
            elif action=="up" and idx>0: layout[idx-1],layout[idx]=layout[idx],layout[idx-1]
            elif action=="down" and idx<len(layout)-1: layout[idx+1],layout[idx]=layout[idx],layout[idx+1]
        _save_json_setting("home_layout",layout); flash("چیدمان صفحه خانه ذخیره شد.","success"); return redirect(url_for("owner_layout"))
    return render_template("owner_layout.html",layout=layout,site=get_site_settings() or default_site(),custom_rows=get_home_custom_rows())

@app.route("/api/site/layout")
def site_layout_api():
    return jsonify({"success":True,"layout":get_home_layout()})

@app.route("/owner/payment-gateways", methods=["GET","POST"])
def owner_payment_gateways():
    guard=owner_required()
    if guard:return guard
    if request.method=="POST":
        driver=(request.form.get("driver") or "manual").strip()
        data={"name":(request.form.get("name") or "").strip() or "درگاه پرداخت",
              "driver":driver,
              "merchant_id":(request.form.get("merchant_id") or "").strip(),
              "api_key":(request.form.get("api_key") or "").strip(),
              "settings_json":request.form.get("settings_json") or "{}",
              "is_active":1 if request.form.get("is_active")=="1" else 0,
              "is_default":1 if request.form.get("is_default")=="1" else 0,
              "sort_order":request.form.get("sort_order",type=int) or 0}
        save_payment_gateway(data, request.form.get("gateway_id",type=int))
        flash("تنظیمات درگاه ذخیره شد.","success")
        return redirect(url_for("owner_payment_gateways"))
    return render_template("owner_payment_gateways.html",gateways=get_payment_gateways(),site=get_site_settings() or default_site())

@app.route("/owner/payment-gateways/<int:gateway_id>/delete",methods=["POST"])
def owner_payment_gateway_delete(gateway_id):
    guard=owner_required()
    if guard:return guard
    conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db"))
    try: conn.execute("DELETE FROM payment_gateways WHERE id=?",(gateway_id,));conn.commit()
    finally:conn.close()
    flash("درگاه حذف شد.","success");return redirect(url_for("owner_payment_gateways"))

# ============================================================
# CONTACT PAGE SETTINGS
# ============================================================

@app.route("/owner/contact/settings", methods=["POST"])
def update_contact_settings():

    guard = owner_required()
    if guard:
        return guard

    title = (request.form.get("contact_title") or "تماس با شهدآور").strip()[:120]
    text = (request.form.get("contact_text") or "").strip()[:1000]
    button = (request.form.get("contact_button_text") or "ارتباط").strip()[:60]

    if not title:
        flash("عنوان صفحه تماس نمی‌تواند خالی باشد.", "error")
        return redirect(url_for("manage_contact"))

    update_site_setting("contact_title", title)
    update_site_setting("contact_text", text)
    update_site_setting("contact_button_text", button or "ارتباط")
    flash("تنظیمات صفحه تماس با موفقیت ذخیره شد.", "success")
    return redirect(url_for("manage_contact"))


# ============================================================
# CONTACT MANAGEMENT
# ============================================================

@app.route(
    "/owner/contact",
    methods=["GET"],
)
def manage_contact():

    guard = owner_required()

    if guard:
        return guard


    site = (
        get_site_settings()
        or default_site()
    )


    methods = get_normalized_contact_methods(
        active_only=False
    )


    return render_template(

        "manage_contacts.html",

        site=site,

        # نسخه‌ای که نام contacts دارد
        # برای قالب فعلی
        contacts=methods,

        # نسخه قبلی برای سازگاری
        contact_methods=methods,

    )


# ============================================================
# ADD CONTACT METHOD
# ============================================================

@app.route(
    "/owner/contact/add",
    methods=["POST"],
)
def add_contact_method_route():

    guard = owner_required()

    if guard:
        return guard


    title = (
        request.form.get(
            "title"
        )
        or ""
    ).strip()


    value = normalize_contact_value(
        request.form.get(
            "value"
        )
    )


    link = normalize_contact_link(
        request.form.get(
            "link"
        )
    )


    icon_emoji = (
        request.form.get(
            "icon_emoji"
        )
        or "📞"
    ).strip()

    platform = (request.form.get("platform") or "custom").strip().lower()
    icon_type = (request.form.get("icon_type") or "emoji").strip().lower()
    if icon_type not in {"emoji", "image"}:
        icon_type = "emoji"
    icon_emoji = default_contact_icon(platform, icon_emoji)
    description = (request.form.get("description") or "").strip()
    button_text = (request.form.get("button_text") or "ارتباط").strip()


    is_active = (
        request.form.get(
            "is_active"
        )
        in {
            "1",
            "true",
            "on",
            "yes",
        }
    )


    # اگر checkbox در قالب بدون value باشد
    if "is_active" not in request.form:

        is_active = False


    if not title:

        flash(
            "عنوان راه ارتباطی را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    if not value:

        flash(
            "شناسه، شماره یا اطلاعات راه ارتباطی را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    sort_order_raw = (request.form.get("sort_order") or "").strip()
    sort_order = _safe_int(sort_order_raw, None) if sort_order_raw else None
    if sort_order is not None:
        sort_order = max(0, min(sort_order, 9999))


    uploaded_icon = request.files.get("icon_file") or request.files.get("icon")


    icon_filename = save_uploaded_file(

        uploaded_icon,

        CONTACT_ICONS_DIR,

        ALLOWED_CONTACT_ICON_EXTENSIONS,

    )


    if (
        uploaded_icon
        and uploaded_icon.filename
        and not icon_filename
    ):

        flash(
            "فرمت تصویر آیکون معتبر نیست. "
            "فرمت‌های مجاز: JPG، PNG، WEBP و GIF",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    try:

        create_contact_compat(

            title=title,

            value=value,

            link=link,

            icon_filename=icon_filename or "",

            icon_emoji=icon_emoji or "📞",
            icon_type=("image" if icon_filename else icon_type),
            platform=platform,
            description=description,
            button_text=button_text,
            sort_order=sort_order,

            is_active=is_active,

        )

    except Exception as error:

        if icon_filename:

            delete_file_if_exists(
                CONTACT_ICONS_DIR,
                icon_filename,
            )

        app.logger.exception(
            "Contact method creation error: %s",
            error,
        )

        flash(
            "راه ارتباطی ایجاد نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    flash(
        "راه ارتباطی جدید با موفقیت اضافه شد.",
        "success",
    )


    return redirect(
        url_for(
            "manage_contact"
        )
    )


# ============================================================
# EDIT CONTACT METHOD
# ============================================================

@app.route(
    "/owner/contact/<int:contact_id>/edit",
    methods=[
        "GET",
        "POST",
    ],
)
def edit_contact_method_route(
    contact_id
):

    guard = owner_required()

    if guard:
        return guard


    contact = get_contact_method(
        contact_id
    )


    if not contact:

        flash(
            "راه ارتباطی موردنظر پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    contact = normalize_contact_record(
        contact
    )


    if request.method == "POST":

        title = (
            request.form.get(
                "title"
            )
            or ""
        ).strip()


        value = normalize_contact_value(
            request.form.get(
                "value"
            )
        )


        link = normalize_contact_link(request.form.get("link"))


        icon_emoji = (
            request.form.get(
                "icon_emoji"
            )
            or contact.get(
                "icon_emoji"
            )
            or "📞"
        ).strip()

        platform = (request.form.get("platform") or contact.get("platform") or "custom").strip().lower()
        icon_type = (request.form.get("icon_type") or contact.get("icon_type") or "emoji").strip().lower()
        if icon_type not in {"emoji", "image"}:
            icon_type = "emoji"
        icon_emoji = default_contact_icon(platform, icon_emoji)
        description = (request.form.get("description") or contact.get("description") or "").strip()
        button_text = (request.form.get("button_text") or contact.get("button_text") or "ارتباط").strip()


        is_active = (
            request.form.get(
                "is_active"
            )
            in {
                "1",
                "true",
                "on",
                "yes",
            }
        )


        if not title:

            flash(
                "عنوان راه ارتباطی الزامی است.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_contact_method_route",
                    contact_id=contact_id,
                )
            )


        if not value:

            flash(
                "شناسه، شماره یا اطلاعات راه ارتباطی الزامی است.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_contact_method_route",
                    contact_id=contact_id,
                )
            )


        sort_order = _safe_int(request.form.get("sort_order"), contact.get("sort_order", 0))


        old_icon = (
            contact.get(
                "icon_filename"
            )
            or contact.get(
                "icon"
            )
            or ""
        )


        uploaded_icon = request.files.get("icon_file") or request.files.get("icon")


        new_icon = save_uploaded_file(

            uploaded_icon,

            CONTACT_ICONS_DIR,

            ALLOWED_CONTACT_ICON_EXTENSIONS,

        )


        if (
            uploaded_icon
            and uploaded_icon.filename
            and not new_icon
        ):

            flash(
                "فرمت تصویر آیکون معتبر نیست. "
                "فرمت‌های مجاز: JPG، PNG، WEBP و GIF",
                "error",
            )

            return redirect(
                url_for(
                    "edit_contact_method_route",
                    contact_id=contact_id,
                )
            )


        remove_icon = (
            request.form.get(
                "remove_icon"
            )
            == "1"
        )


        if new_icon:

            icon_filename = new_icon

        elif remove_icon:

            icon_filename = ""

        else:

            icon_filename = old_icon


        try:

            update_contact_compat(

                contact_id=contact_id,

                title=title,

                value=value,

                link=link,

                icon_filename=icon_filename,

                icon_emoji=icon_emoji or "📞",
                icon_type=("image" if icon_filename else icon_type),
                platform=platform,
                description=description,
                button_text=button_text,

                is_active=is_active,
                sort_order=sort_order,

            )

        except Exception as error:

            if new_icon:

                delete_file_if_exists(
                    CONTACT_ICONS_DIR,
                    new_icon,
                )

            app.logger.exception(
                "Contact method update error: %s",
                error,
            )

            flash(
                "ویرایش راه ارتباطی انجام نشد.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_contact_method_route",
                    contact_id=contact_id,
                )
            )


        if new_icon and old_icon:

            delete_file_if_exists(
                CONTACT_ICONS_DIR,
                old_icon,
            )

        elif remove_icon and old_icon:

            delete_file_if_exists(
                CONTACT_ICONS_DIR,
                old_icon,
            )


        flash(
            "راه ارتباطی با موفقیت ویرایش شد.",
            "success",
        )


        return redirect(
            url_for(
                "manage_contact"
            )
        )


    return render_template(

        "edit_contact.html",

        contact=contact,

    )


# ============================================================
# DELETE CONTACT METHOD
# ============================================================

@app.route(
    "/owner/contact/<int:contact_id>/delete",
    methods=["POST"],
)
def delete_contact_method_route(
    contact_id
):

    guard = owner_required()

    if guard:
        return guard


    contact = get_contact_method(
        contact_id
    )


    if not contact:

        flash(
            "راه ارتباطی پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    contact = normalize_contact_record(
        contact
    )


    deleted = delete_contact_method(
        contact_id
    )


    if deleted:

        deleted = normalize_contact_record(
            deleted
        )


        delete_file_if_exists(
            CONTACT_ICONS_DIR,
            (
                deleted.get(
                    "icon_filename"
                )
                or contact.get(
                    "icon_filename"
                )
            ),
        )


        flash(
            "راه ارتباطی حذف شد.",
            "success",
        )

    else:

        flash(
            "راه ارتباطی پیدا نشد.",
            "error",
        )


    return redirect(
        url_for(
            "manage_contact"
        )
    )


# ============================================================
# TOGGLE CONTACT METHOD
# ============================================================

@app.route(
    "/owner/contact/<int:contact_id>/toggle",
    methods=["POST"],
)
def toggle_contact_method_route(
    contact_id
):

    guard = owner_required()

    if guard:
        return guard


    contact = get_contact_method(
        contact_id
    )


    if not contact:

        flash(
            "راه ارتباطی پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    current_status = bool(
        contact.get(
            "is_active",
            1,
        )
    )


    toggle_contact_method(
        contact_id,
        not current_status,
    )


    if current_status:

        flash(
            "راه ارتباطی غیرفعال شد.",
            "success",
        )

    else:

        flash(
            "راه ارتباطی فعال شد.",
            "success",
        )


    return redirect(
        url_for(
            "manage_contact"
        )
    )


# ============================================================
# MOVE CONTACT METHOD
# ============================================================

@app.route(
    "/owner/contact/<int:contact_id>/move/<direction>",
    methods=["POST"],
)
def move_contact_method_route(
    contact_id,
    direction,
):

    guard = owner_required()

    if guard:
        return guard


    if direction not in {
        "up",
        "down",
    }:

        flash(
            "جهت جابه‌جایی نامعتبر است.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    contact = get_contact_method(
        contact_id
    )


    if not contact:

        flash(
            "راه ارتباطی پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "manage_contact"
            )
        )


    try:

        moved = move_contact_method(
            contact_id,
            direction,
        )

    except Exception as error:

        app.logger.exception(
            "Contact method move error: %s",
            error,
        )

        moved = False


    if not moved:

        if direction == "up":

            flash(
                "این مورد در بالاترین جایگاه قرار دارد.",
                "info",
            )

        else:

            flash(
                "این مورد در پایین‌ترین جایگاه قرار دارد.",
                "info",
            )

    else:

        flash(
            "ترتیب راه‌های ارتباطی به‌روزرسانی شد.",
            "success",
        )


    return redirect(
        url_for(
            "manage_contact"
        )
    )


# ============================================================
# BANNERS
# ============================================================

@app.route("/owner/banners", methods=["GET", "POST"])
def manage_banners():
    guard = owner_required()
    if guard: return guard
    if request.method == "POST":
        banners = get_banners() or []
        if len(banners) >= 5:
            flash("حداکثر ۵ بنر برای بخش محصولات مجاز است.", "error")
            return redirect(url_for("manage_banners"))
        filename = save_uploaded_file(request.files.get("banner"), BANNERS_DIR, ALLOWED_IMAGE_EXTENSIONS)
        if not filename:
            flash("لطفاً یک تصویر معتبر (JPG/PNG/WEBP) انتخاب کنید.", "error")
            return redirect(url_for("manage_banners"))
        title = (request.form.get("title") or "").strip()[:200]
        link = normalize_contact_link((request.form.get("link") or "").strip())
        if link and not urlparse(link).scheme:
            link = ""
        add_banner(filename, title, link)
        flash("بنر با موفقیت اضافه شد.", "success")
        return redirect(url_for("manage_banners"))
    return render_template("manage_banners.html", banners=get_banners() or [])


@app.route("/owner/banners/<int:banner_id>/update", methods=["POST"])
def update_banner_route(banner_id):
    guard = owner_required()
    if guard: return guard
    current = next((b for b in (get_banners() or []) if b.get("id") == banner_id), None)
    if not current:
        flash("بنر پیدا نشد.", "error")
        return redirect(url_for("manage_banners"))
    new_file = save_uploaded_file(request.files.get("banner"), BANNERS_DIR, ALLOWED_IMAGE_EXTENSIONS)
    filename = new_file or current.get("filename")
    title = (request.form.get("title") or "").strip()[:200]
    link = normalize_contact_link(request.form.get("link"))
    if not update_banner(banner_id, filename, title, link):
        if new_file: delete_file_if_exists(BANNERS_DIR, new_file)
        flash("ویرایش بنر انجام نشد.", "error")
    else:
        if new_file: delete_file_if_exists(BANNERS_DIR, current.get("filename"))
        flash("بنر به‌روزرسانی شد.", "success")
    return redirect(url_for("manage_banners"))


@app.route("/owner/banners/<int:banner_id>/toggle", methods=["POST"])
def toggle_banner_route(banner_id):
    guard = owner_required()
    if guard: return guard
    changed = toggle_banner(banner_id)
    flash("وضعیت بنر به‌روزرسانی شد." if changed else "بنر پیدا نشد.", "success" if changed else "error")
    return redirect(url_for("manage_banners"))


@app.route("/owner/banners/<int:banner_id>/move/<direction>", methods=["POST"])
def move_banner_route(banner_id, direction):
    guard = owner_required()
    if guard: return guard
    moved = move_banner(banner_id, direction)
    flash("ترتیب بنرها به‌روزرسانی شد." if moved else "این بنر در این جهت جای دیگری ندارد.", "success" if moved else "info")
    return redirect(url_for("manage_banners"))


@app.route("/owner/banners/<int:banner_id>/delete", methods=["POST"])
def delete_banner_route(banner_id):
    guard = owner_required()
    if guard: return guard
    banner = delete_banner(banner_id)
    if banner:
        delete_file_if_exists(BANNERS_DIR, banner.get("filename"))
        flash("بنر حذف شد.", "success")
    else:
        flash("بنر پیدا نشد.", "error")
    return redirect(url_for("manage_banners"))


# ============================================================
# REVIEWS
# ============================================================

@app.route(
    "/product/<int:product_id>/review",
    methods=["POST"],
)
def submit_review(
    product_id
):

    if not session.get(
        "user_id"
    ):

        flash(
            "برای ثبت نظر ابتدا وارد حساب کاربری خود شوید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    product = get_normalized_product(
        product_id
    )


    if not product:

        flash(
            "محصول موردنظر پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "products_page"
            )
        )


    comment = (
        request.form.get(
            "comment"
        )
        or ""
    ).strip()
    try:
        rating = max(1, min(5, int(request.form.get("rating", "5"))))
    except (TypeError, ValueError):
        rating = 5


    if not comment:

        flash(
            "لطفاً متن نظر را وارد کنید.",
            "error",
        )

        return redirect(
            url_for(
                "product_detail",
                product_id=product_id,
            )
        )


    if len(comment) > 1000:

        flash(
            "متن نظر نمی‌تواند بیشتر از ۱۰۰۰ کاراکتر باشد.",
            "error",
        )

        return redirect(
            url_for(
                "product_detail",
                product_id=product_id,
            )
        )


    create_review(

        product_id=product_id,

        user_id=session.get(
            "user_id"
        ),

        comment=comment,
        rating=rating,

    )


    flash(
        "نظر شما با موفقیت ثبت شد و پس از تأیید مالک نمایش داده می‌شود.",
        "success",
    )


    return redirect(
        url_for(
            "product_detail",
            product_id=product_id,
        )
    )


# ============================================================
# REVIEW MANAGEMENT
# ============================================================

@app.route("/owner/reviews")
def manage_reviews():
    guard = owner_required()
    if guard: return guard
    site = get_site_settings() or default_site()
    status = (request.args.get("status") or "pending").strip().lower()
    if status not in {"all", "pending", "approved", "rejected", "replied"}:
        status = "all"
    reviews = get_all_reviews(None if status == "all" else status)
    return render_template("manage_reviews.html", site=site, reviews=reviews, active_status=status, pending_reviews_count=get_pending_reviews_count())

@app.route("/owner/reviews/approved")
def approved_reviews_page():
    guard=owner_required()
    if guard:return guard
    site=get_site_settings() or default_site()
    reviews=get_all_reviews("approved") + get_all_reviews("replied")
    return render_template("manage_reviews.html",site=site,reviews=reviews,active_status="approved_only",pending_reviews_count=get_pending_reviews_count(),approved_page=True)

@app.route("/owner/reviews/<int:review_id>/status", methods=["POST"])
def update_review_status(review_id):
    guard = owner_required()
    if guard: return guard
    status = (request.form.get("status") or "").strip().lower()
    if status not in {"approved", "rejected", "pending", "replied"}:
        flash("وضعیت نظر نامعتبر است.", "error")
    elif set_review_status(review_id, status):
        flash("وضعیت نظر به‌روزرسانی شد.", "success")
    else:
        flash("نظر پیدا نشد.", "error")
    return redirect(url_for("manage_reviews"))

@app.route("/owner/reviews/<int:review_id>/reply", methods=["POST"])
def reply_review_page(review_id):
    guard = owner_required()
    if guard: return guard
    reply = (request.form.get("reply") or "").strip()
    approve_with_reply = request.form.get("approve_with_reply") == "1"
    if len(reply) > 1000:
        flash("پاسخ نمی‌تواند بیشتر از ۱۰۰۰ کاراکتر باشد.", "error")
    elif not reply:
        flash("متن پاسخ را وارد کنید.", "error")
    elif set_review_reply(review_id, reply):
        review = get_review(review_id)
        if approve_with_reply:
            set_review_status(review_id, "replied")
            flash("نظر تأیید و پاسخ مالک منتشر شد.", "success")
        elif review and review.get("status") == "approved":
            set_review_status(review_id, "replied")
            flash("پاسخ مالک ذخیره و نظر در وضعیت پاسخ‌داده‌شده قرار گرفت.", "success")
        else:
            flash("پاسخ مالک ذخیره شد؛ نظر تا زمان تأیید عمومی نمی‌شود.", "success")
    else:
        flash("نظر پیدا نشد.", "error")
    return redirect(url_for("manage_reviews"))

@app.route("/owner/reviews/<int:review_id>/delete", methods=["POST"])
def delete_review_page(review_id):
    guard = owner_required()
    if guard: return guard
    if delete_review(review_id): flash("نظر حذف شد.", "success")
    else: flash("نظر پیدا نشد.", "error")
    return redirect(url_for("manage_reviews"))



# ============================================================
# SUPPORT MEDIA
# ============================================================

def _save_support_media(file):
    if not file or not file.filename:
        return '', ''
    filename=secure_filename(file.filename)
    if not filename:return '',''
    ext=Path(filename).suffix.lower()
    allowed={
        '.jpg','.jpeg','.png','.webp','.gif','.bmp','.svg',
        '.mp4','.webm','.mov','.m4v','.avi','.mkv',
        '.mp3','.wav','.ogg','.m4a','.aac','.flac',
        '.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.zip','.rar'
    }
    if ext not in allowed:return None,None
    try:
        pos=file.stream.tell();file.stream.seek(0,os.SEEK_END);size=file.stream.tell();file.stream.seek(pos)
    except Exception:return None,None
    if size<=0 or size>50*1024*1024:return None,None
    name=f"{secrets.token_hex(16)}{ext}"
    file.save(SUPPORT_MEDIA_DIR/name)
    if ext in {'.jpg','.jpeg','.png','.webp','.gif','.bmp','.svg'}: typ='image'
    elif ext in {'.mp4','.webm','.mov','.m4v','.avi','.mkv'}: typ='video'
    elif ext in {'.mp3','.wav','.ogg','.m4a','.aac','.flac'}: typ='voice'
    else: typ='file'
    return f"support/{name}",typ

# ============================================================
# CUSTOMER SUPPORT
# ============================================================

@app.route("/api/support/messages", methods=["GET"])
def support_messages_api():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"success":False,"message":"ابتدا وارد حساب شوید."}), 401
    conv = get_or_create_support_conversation(user_id)
    mark_support_messages_read(conv["id"], "user")
    return jsonify({"success":True,"conversation":conv,"messages":get_support_messages(conv["id"])})

@app.route("/api/support/messages", methods=["POST"])
def support_send_message_api():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"success":False,"message":"ابتدا وارد حساب شوید."}), 401
    message=(request.form.get("message") or "").strip()
    if not message and not request.files.get("media"): return jsonify({"success":False,"message":"پیام خالی است."}),400
    if len(message)>4000:return jsonify({"success":False,"message":"پیام خیلی طولانی است."}),400
    conv=get_or_create_support_conversation(user_id)
    reply_to=request.form.get("reply_to_message_id",type=int)
    attachment_path=''; attachment_type=''; valid=[]
    for media in request.files.getlist("media")[:10]:
        if media and media.filename:
            p,t=_save_support_media(media)
            if p is None:return jsonify({"success":False,"message":"یکی از فایل‌ها نوع یا حجم مجاز ندارد."}),400
            valid.append((p,t))
    if valid: attachment_path,attachment_type=valid[0]
    mid=add_support_message(conv["id"],"user",user_id,message or ('📷 تصاویر پیوست' if len(valid)>1 else ('🎙️ پیام صوتی' if attachment_type=='voice' else '📎 فایل پیوست')),reply_to_message_id=reply_to)
    if valid and mid:
        conn=sqlite3.connect(str(BASE_DIR/'honeyshop.db'));conn.execute("UPDATE support_messages SET attachment_path=?,attachment_type=?,attachment_paths=? WHERE id=?",(attachment_path,attachment_type,json.dumps([p for p,_ in valid],ensure_ascii=False),mid));conn.commit();conn.close()
    return jsonify({"success":True,"messages":get_support_messages(conv["id"])})

@app.route("/api/support/messages/<int:message_id>", methods=["PUT","DELETE"])
def support_message_mutation(message_id):
    user_id=session.get("user_id")
    if not user_id:return jsonify({"success":False}),401
    if request.method=="PUT":
        data=request.get_json(silent=True) or {}; message=(data.get('message') or '').strip()
        if not message:return jsonify({"success":False,"message":"متن خالی است."}),400
        ok=update_support_message(message_id,'user',user_id,message)
    else: ok=delete_support_message(message_id,'user',user_id)
    return jsonify({"success":ok})

@app.route("/owner/messages")
def owner_messages():
    guard=owner_required()
    if guard: return guard
    conversations=get_support_conversations()
    selected_id=request.args.get("conversation", type=int)
    selected=get_support_conversation(selected_id) if selected_id else (conversations[0] if conversations else None)
    messages=get_support_messages(selected["id"]) if selected else []
    if selected: mark_support_messages_read(selected["id"], "user")
    return render_template("owner_messages.html", conversations=conversations, selected=selected, messages=messages, unread_count=get_unread_support_count(), support_branding=_support_branding())

@app.route("/owner/messages/<int:conversation_id>/reply", methods=["POST"])
def owner_support_reply(conversation_id):
    guard=owner_required()
    if guard: return guard
    conversation = get_support_conversation(conversation_id)
    if not conversation:
        flash("گفت‌وگو پیدا نشد.", "error")
        return redirect(url_for("owner_messages"))
    message=(request.form.get("message") or "").strip()
    if len(message) > 4000:
        flash("پیام خیلی طولانی است.", "error")
    elif message:
        reply_to = request.form.get("reply_to_message_id", type=int)
        add_support_message(conversation_id, "owner", "owner", message, reply_to_message_id=reply_to)
    return redirect(url_for("owner_messages", conversation=conversation_id))


@app.route("/owner/messages/<int:conversation_id>/message", methods=["POST"])
def owner_support_message_action(conversation_id):
    guard=owner_required()
    if guard:return guard
    message=(request.form.get("message") or "").strip(); valid=[]
    for media in request.files.getlist('media')[:10]:
        if media and media.filename:
            p,t=_save_support_media(media)
            if p is None: flash('یکی از فایل‌ها نوع یا حجم مجاز ندارد.','error'); return redirect(url_for('owner_messages',conversation=conversation_id))
            valid.append((p,t))
    attachment_path,attachment_type=(valid[0] if valid else ('',''))
    if message or valid:
        mid=add_support_message(conversation_id,'owner','owner',message or ('📷 تصاویر پیوست' if len(valid)>1 else ('🎙️ پیام صوتی' if attachment_type=='voice' else '📎 فایل پیوست')),request.form.get('reply_to_message_id',type=int))
        if valid:
            conn=sqlite3.connect(str(BASE_DIR/'honeyshop.db'));conn.execute("UPDATE support_messages SET attachment_path=?,attachment_type=?,attachment_paths=? WHERE id=?",(attachment_path,attachment_type,json.dumps([p for p,_ in valid],ensure_ascii=False),mid));conn.commit();conn.close()
    return redirect(url_for('owner_messages',conversation=conversation_id))

@app.route("/api/owner/messages/<int:message_id>/pin", methods=["POST"])
def owner_support_message_pin(message_id):
    guard=owner_required()
    if guard:return guard
    pinned=(request.form.get("pinned") or "0") in {"1","true","on","yes"}
    ok=pin_support_message(message_id,pinned)
    return jsonify({"success":bool(ok),"pinned":pinned})


@app.route("/api/owner/messages/<int:message_id>", methods=["PUT","DELETE"])
def owner_support_message_mutation(message_id):
    guard=owner_required()
    if guard:return guard
    if request.method=='PUT':
        data=request.get_json(silent=True) or {};ok=update_support_message_as_owner(message_id,(data.get('message') or '').strip())
    else: ok=delete_support_message_as_owner(message_id)
    return jsonify({'success':ok})

@app.route("/api/owner/messages/<int:conversation_id>")
def owner_messages_api(conversation_id):
    guard = owner_required()
    if guard: return guard
    conversation = get_support_conversation(conversation_id)
    if not conversation:
        return jsonify({"success": False, "message": "گفت‌وگو پیدا نشد."}), 404
    mark_support_messages_read(conversation_id, "user")
    return jsonify({"success": True, "conversation": conversation, "messages": get_support_messages(conversation_id)})


# ============================================================
# SUPPORT ORDER STATUS / BRANDING
# ============================================================

@app.route("/owner/messages/order/<int:order_id>/status", methods=["POST"])
def owner_support_order_status(order_id):
    guard=owner_required()
    if guard:return guard
    state=(request.form.get("state") or "").strip().lower()
    order=get_order_by_id(order_id)
    if not order:
        return jsonify({"success":False,"message":"سفارش پیدا نشد."}),404
    if state == "success":
        ok=update_order_status(order_id,"completed","paid")
    elif state == "failed":
        ok=update_order_status(order_id,"cancelled","failed")
    else:
        ok=False
    return jsonify({"success":bool(ok),"state":state})


@app.route("/owner/support-branding", methods=["GET","POST"])
def owner_support_branding():
    guard=owner_required()
    if guard:return guard
    site=get_site_settings() or default_site()
    if request.method=="POST":
        profile=save_uploaded_file(request.files.get("support_profile_image"), SUPPORT_BRANDING_DIR, ALLOWED_IMAGE_EXTENSIONS)
        background=save_uploaded_file(request.files.get("support_background_image"), SUPPORT_BRANDING_DIR, ALLOWED_IMAGE_EXTENSIONS)
        old_profile=site.get("support_profile_image") or ""; old_background=site.get("support_background_image") or ""
        if profile:
            update_site_setting("support_profile_image",profile)
            if old_profile: delete_file_if_exists(SUPPORT_BRANDING_DIR,old_profile)
        if background:
            update_site_setting("support_background_image",background)
            if old_background: delete_file_if_exists(SUPPORT_BRANDING_DIR,old_background)
        if request.form.get("remove_background")=="1":
            update_site_setting("support_background_image","")
            if old_background: delete_file_if_exists(SUPPORT_BRANDING_DIR,old_background)
        display_name=(request.form.get("support_display_name") or "پشتیبانی شهدآور").strip()[:80]
        profile_text=(request.form.get("support_profile_text") or "پاسخ‌گویی و هماهنگی سفارش‌های شهدآور").strip()[:220]
        update_site_setting("support_display_name", display_name or "پشتیبانی شهدآور")
        update_site_setting("support_profile_text", profile_text or "پاسخ‌گویی و هماهنگی سفارش‌های شهدآور")
        update_site_setting("support_popup_text", (request.form.get("support_popup_text") or "پشتیبانی شهدآور: سوالی دارید در خدمتم!").strip()[:180])
        update_site_setting("support_popup_color", (request.form.get("support_popup_color") or "#d9a62e").strip()[:20])
        update_site_setting("support_popup_enabled", "1" if request.form.get("support_popup_enabled")=="1" else "0")
        flash("پروفایل و پیام شناور پشتیبانی به‌روزرسانی شد.","success")
        return redirect(url_for("owner_support_branding"))
    return render_template("owner_support_branding.html",site=site,support_branding=_support_branding())


# ============================================================
# CUSTOMER / OWNER USER MANAGEMENT
# ============================================================

@app.route("/owner/users")
def owner_users():
    guard=owner_required()
    if guard: return guard
    q=(request.args.get("q") or "").strip()
    users=get_users()
    if q:
        qn=normalize_phone(q)
        users=[u for u in users if q.lower() in str(u.get("username") or "").lower() or q.lower() in str(u.get("email") or "").lower() or q.lower() in str(u.get("first_name") or "").lower() or q.lower() in str(u.get("last_name") or "").lower() or qn==normalize_phone(u.get("phone"))]
    return render_template("owner_users.html", users=users, q=q, user_count=get_user_count())

@app.route("/owner/users/<int:user_id>", methods=["GET","POST"])
def owner_user_profile(user_id):
    guard=owner_required()
    if guard: return guard
    user=get_user_by_id(user_id)
    if not user:
        flash("کاربر پیدا نشد.","error"); return redirect(url_for("owner_users"))
    if request.method=="POST":
        first=(request.form.get("first_name") or "").strip(); last=(request.form.get("last_name") or "").strip(); phone=normalize_phone(request.form.get("phone")); email=(request.form.get("email") or "").strip(); province=(request.form.get("province") or "").strip(); city=(request.form.get("city") or "").strip(); gender=(request.form.get("gender") or user.get("gender") or "").strip(); username=(request.form.get("username") or "").strip()
        if not first or not last or not is_valid_phone(phone) or (username and not is_username_available(username,user_id)):
            flash("اطلاعات واردشده معتبر نیست یا نام کاربری تکراری است.","error")
        else:
            try:
                update_user(user_id,first,last,phone,email,province,city,gender,username)
                new_password=(request.form.get("new_password") or "").strip()
                if new_password: update_user_password(user_id,generate_password_hash(new_password))
                flash("اطلاعات کاربر با موفقیت به‌روزرسانی شد.","success")
                user=get_user_by_id(user_id)
            except sqlite3.IntegrityError:
                flash("این شماره موبایل قبلاً ثبت شده است.","error")
    return render_template("user_profile.html", user=user, owner_mode=True)

# ============================================================
# CART / CHECKOUT / ORDERS
# ============================================================

def _cart_required():
    user_id=session.get("user_id")
    if not user_id: return None, (jsonify({"success":False,"message":"برای استفاده از سبد خرید وارد حساب شوید.","redirect":"/account"}),401)
    return user_id,None

@app.route("/cart")
def cart_page():
    user_id=session.get("user_id")
    if not user_id: return redirect(url_for("account", next="/cart"))
    items,total=get_cart(user_id)
    return render_template("cart.html",items=items,subtotal=total,total=total)

@app.route("/api/cart/summary")
def cart_summary_api():
    user_id=session.get("user_id")
    if not user_id:return jsonify({"success":True,"count":0,"total":0})
    items,total=get_cart(user_id)
    return jsonify({"success":True,"count":sum(int(i['quantity']) for i in items),"total":total})

@app.route("/api/cart/add", methods=["POST"])
def cart_add_api():
    user_id,error=_cart_required()
    if error:return error
    data=request.get_json(silent=True) or request.form
    try: product_id=int(data.get("product_id")); quantity=max(1,int(data.get("quantity",1)))
    except (TypeError,ValueError): return jsonify({"success":False,"message":"اطلاعات محصول نامعتبر است."}),400
    ok,result=upsert_cart_item(user_id,product_id,quantity)
    if not ok:return jsonify({"success":False,"message":result}),400
    items,total=get_cart(user_id)
    return jsonify({"success":True,"message":"محصول به سبد خرید اضافه شد.","count":sum(int(i['quantity']) for i in items),"total":total})

@app.route("/api/cart/update", methods=["POST"])
def cart_update_api():
    user_id,error=_cart_required()
    if error:return error
    data=request.get_json(silent=True) or request.form
    try: product_id=int(data.get("product_id")); quantity=int(data.get("quantity",1))
    except (TypeError,ValueError): return jsonify({"success":False,"message":"مقدار نامعتبر است."}),400
    update_cart_quantity(user_id,product_id,quantity)
    items,total=get_cart(user_id); return jsonify({"success":True,"items":items,"subtotal":total,"total":total,"count":sum(int(i['quantity']) for i in items)})

@app.route("/api/cart/remove", methods=["POST"])
def cart_remove_api():
    user_id,error=_cart_required()
    if error:return error
    data=request.get_json(silent=True) or request.form
    try: product_id=int(data.get("product_id"))
    except (TypeError,ValueError): return jsonify({"success":False,"message":"محصول نامعتبر است."}),400
    remove_cart_item(user_id,product_id); items,total=get_cart(user_id); return jsonify({"success":True,"items":items,"subtotal":total,"total":total,"count":sum(int(i['quantity']) for i in items)})

@app.route("/api/cart/clear", methods=["POST"])
def cart_clear_api():
    user_id,error=_cart_required()
    if error:return error
    clear_cart(user_id); return jsonify({"success":True})

@app.route("/checkout", methods=["GET","POST"])
def checkout_page():
    user_id=session.get("user_id")
    if not user_id:return redirect(url_for("account",next="/checkout"))
    items,total=get_cart(user_id)
    if not items:
        flash("سبد خرید شما خالی است.","error"); return redirect(url_for("cart_page"))
    if request.method=="POST":
        method=(request.form.get("payment_method") or "seller_coordination").strip()
        address=(request.form.get("address") or "").strip(); notes=(request.form.get("notes") or "").strip()
        if not address:
            flash("آدرس یا توضیحات تحویل را وارد کنید.","error")
        else:
            order_number,error=create_order_from_cart(user_id,method,address,notes)
            if error:
                flash(error,"error")
            else:
                conv = get_or_create_support_conversation(user_id)
                lines=[f'🧾 سفارش جدید — {order_number}', f'روش خرید: {"هماهنگی با پشتیبانی" if method == "seller_coordination" else "پرداخت آنلاین"}', '']
                for item in items:
                    lines.append(f'🍯 {item.get("title","")} × {item.get("quantity",1)} | قیمت واحد: {int(item.get("unit_price") or 0):,} تومان | جمع: {int(item.get("line_total") or 0):,} تومان')
                lines += ['', f'💰 جمع نهایی: {int(total):,} تومان', '🚚 هزینه ارسال با خریدار است و جداگانه هماهنگ می‌شود.', f'📍 اطلاعات تحویل: {address}']
                if notes: lines.append(f'📝 یادداشت: {notes}')
                mid=add_support_message(conv['id'],'user',user_id,'\n'.join(lines))
                order = get_order_by_number(order_number, user_id)
                if mid:
                    set_support_message_meta(mid, is_pinned=True, order_id=(order or {}).get('id'))
                    # Send every product image as a compact, individually zoomable message.
                    # The main invoice/order card stays pinned as the canonical order message.
                    for item in items:
                        image_name=item.get('image_1') or ''
                        if image_name:
                            image_mid=add_support_message(conv['id'],'user',user_id,f"📷 تصویر محصول: {item.get('title','')}")
                            if image_mid:
                                set_support_message_meta(image_mid, is_pinned=True, order_id=(order or {}).get('id'))
                                conn=sqlite3.connect(str(BASE_DIR/'honeyshop.db')); conn.execute("UPDATE support_messages SET attachment_path=?,attachment_type='image' WHERE id=?",(f"products/{image_name}",image_mid)); conn.commit(); conn.close()
                order = order or get_order_by_number(order_number, user_id)
                sent, notify_errors, notify_message = send_order_notification(order or {}, items)
                if method == 'seller_coordination':
                    flash('سفارش ثبت شد؛ فاکتور و تصاویر محصولات داخل گفت‌وگوی پشتیبانی سنجاق شد.','success')
                    return redirect(url_for("support_page"))
                else:
                    flash('سفارش آنلاین ثبت شد و در تاریخچه خرید قابل پیگیری است.','success')
                    return redirect(url_for("order_success",order_number=order_number))
    return render_template("checkout.html",items=items,subtotal=total,total=total)

@app.route("/owner/orders")
def owner_orders():
    guard=owner_required()
    if guard:return guard
    return render_template("owner_orders.html",orders=get_all_orders())

@app.route("/owner/orders/<int:order_id>/status",methods=["POST"])
def owner_order_status(order_id):
    guard=owner_required()
    if guard:return guard
    status=(request.form.get("status") or "pending").strip()
    payment_status=request.form.get("payment_status") or None
    if update_order_status(order_id,status,payment_status):flash("وضعیت سفارش به‌روزرسانی شد.","success")
    else:flash("سفارش پیدا نشد.","error")
    return redirect(url_for("owner_orders"))

@app.route("/orders")
def order_history():
    user_id=session.get("user_id")
    if not user_id:return redirect(url_for("account",next="/orders"))
    orders=get_user_orders(user_id)
    return render_template("orders.html",orders=orders, support_orders=[o for o in orders if o.get("payment_method")=="seller_coordination"], online_orders=[o for o in orders if o.get("payment_method")=="online"])

@app.route("/orders/<order_number>/remind", methods=["POST"])
def order_reminder(order_number):
    user_id=session.get("user_id")
    if not user_id:
        return redirect(url_for("account", next=url_for("order_history")))
    order=get_order_by_number(order_number,user_id)
    if not order:
        flash("سفارش پیدا نشد.","error")
        return redirect(url_for("order_history"))
    if order.get("payment_method") != "seller_coordination":
        flash("یادآوری فقط برای خرید با پشتیبانی فعال است.","error")
        return redirect(url_for("order_history"))
    conv=get_or_create_support_conversation(user_id)
    items=order.get("items") or []
    lines=[f'🔔 یادآوری سفارش — {order_number}', 'روش خرید: هماهنگی با پشتیبانی', '']
    for item in items:
        lines.append(f'🍯 {item.get("product_title","")} × {item.get("quantity",1)} | جمع: {int(item.get("line_total") or 0):,} تومان')
    lines += ['', f'💰 مبلغ نهایی: {int(order.get("total_amount") or 0):,} تومان', 'لطفاً وضعیت این سفارش را بررسی و در صورت نیاز تأیید کنید.']
    mid=add_support_message(conv["id"],"user",user_id,"\n".join(lines))
    if mid:
        set_support_message_meta(mid,is_pinned=True,order_id=order.get("id"))
        for item in items:
            image_name=item.get("image_1") or ""
            if image_name:
                imid=add_support_message(conv["id"],"user",user_id,f"📷 تصویر محصول: {item.get('product_title','')}")
                if imid:
                    set_support_message_meta(imid,is_pinned=True,order_id=order.get("id"))
                    conn=sqlite3.connect(str(BASE_DIR/'honeyshop.db'));conn.execute("UPDATE support_messages SET attachment_path=?,attachment_type='image' WHERE id=?",(f"products/{image_name}",imid));conn.commit();conn.close()
    flash("یادآوری سفارش دوباره برای پشتیبانی ارسال شد.","success")
    return redirect(url_for("support_page"))

@app.route("/orders/<order_number>")
def order_success(order_number):
    user_id=session.get("user_id")
    if not user_id:return redirect(url_for("account"))
    order=get_order_by_number(order_number,user_id)
    if not order:return redirect(url_for("order_history"))
    return render_template("order_success.html",order=order,site=get_site_settings() or default_site())

# ============================================================
# PASSWORD RECOVERY CHAT
# ============================================================

@app.route("/account/forgot-password")
def forgot_password_page():
    if session.get("user_id"):
        return redirect(url_for("account"))
    conv=get_recovery_conversation(session.get("recovery_conversation_id")) if session.get("recovery_conversation_id") else None
    if not conv:
        conv=get_or_create_recovery_conversation(None,"")
        session["recovery_conversation_id"]=conv["id"]
    return render_template("recovery_chat.html",conversation=conv,owner_mode=False)

@app.route("/api/recovery/messages", methods=["GET","POST"])
def recovery_messages_api():
    user_id=session.get("user_id")
    if user_id:
        conv=get_or_create_recovery_conversation(user_id,normalize_phone(request.values.get("phone") or request.form.get("phone") or ""))
    else:
        conv=get_recovery_conversation(session.get("recovery_conversation_id")) if session.get("recovery_conversation_id") else None
        if not conv:
            conv=get_or_create_recovery_conversation(None,normalize_phone(request.values.get("phone") or request.form.get("phone") or ""))
            session["recovery_conversation_id"]=conv["id"]
        phone=normalize_phone(request.values.get("phone") or request.form.get("phone") or "")
        if phone:
            conn=sqlite3.connect(str(BASE_DIR/'honeyshop.db'));conn.execute("UPDATE recovery_conversations SET visitor_phone=? WHERE id=?",(phone,conv['id']));conn.commit();conn.close();conv=get_recovery_conversation(conv['id'])
    if request.method=="GET":
        mark_recovery_read(conv['id'],'owner' if session.get('is_owner') else 'user')
        return jsonify({"success":True,"conversation":conv,"messages":get_recovery_messages(conv['id'])})
    data=request.get_json(silent=True) or request.form
    message=(data.get('message') or '').strip()
    if not message:return jsonify({"success":False,"message":"پیام خالی است."}),400
    reply_to=data.get('reply_to_message_id')
    try: reply_to=int(reply_to) if reply_to else None
    except: reply_to=None
    add_recovery_message(conv['id'],'user' if not session.get('is_owner') else 'owner',user_id or 'visitor',message,reply_to)
    return jsonify({"success":True,"messages":get_recovery_messages(conv['id'])})

@app.route("/owner/recovery")
def owner_recovery():
    guard=owner_required()
    if guard:return guard
    conversations=get_recovery_conversations(); selected_id=request.args.get('conversation',type=int); selected=next((c for c in conversations if c['id']==selected_id),None) if selected_id else (conversations[0] if conversations else None); messages=get_recovery_messages(selected['id']) if selected else []
    if selected:mark_recovery_read(selected['id'],'user')
    return render_template('owner_recovery.html',conversations=conversations,selected=selected,messages=messages,unread_count=get_unread_recovery_count())

@app.route("/owner/recovery/<int:conversation_id>/reply",methods=['POST'])
def owner_recovery_reply(conversation_id):
    guard=owner_required()
    if guard:return guard
    message=(request.form.get('message') or '').strip()
    if message:add_recovery_message(conversation_id,'owner','owner',message,request.form.get('reply_to_message_id',type=int))
    return redirect(url_for('owner_recovery',conversation=conversation_id))

@app.route("/owner/recovery/<int:conversation_id>/delete",methods=['POST'])
def owner_recovery_delete(conversation_id):
    guard=owner_required()
    if guard:return guard
    delete_recovery_conversation(conversation_id); flash('گفت‌وگوی فراموشی رمز حذف شد.','success'); return redirect(url_for('owner_recovery'))

# ============================================================
# SEO / GOOGLE SEARCH READINESS
# ============================================================

@app.route('/robots.txt')
def robots_txt():
    base=app.config['SITE_PUBLIC_URL']; return (f"User-agent: *\nAllow: /\nDisallow: /owner\nDisallow: /api/\nDisallow: /account/forgot-password\nSitemap: {base}/sitemap.xml\n",200,{'Content-Type':'text/plain; charset=utf-8'})

@app.route('/sitemap.xml')
def sitemap_xml():
    base=app.config['SITE_PUBLIC_URL']; urls=[f"{base}/",f"{base}/pages/products.html",f"{base}/pages/about.html",f"{base}/pages/support.html",f"{base}/pages/contact.html",f"{base}/pages/faq.html",f"{base}/pages/profiles.html",f"{base}/pages/knowledge.html"]
    urls += [f"{base}/product/{p['id']}" for p in get_all_normalized_products() if p.get('is_available',True)]
    urls += [f"{base}/profile/{p['slug']}" for p in get_profiles(published_only=True)]
    urls += [f"{base}/knowledge/{a['slug']}" for a in get_knowledge_articles(published_only=True)]
    body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{html_lib.escape(u)}</loc></url>' for u in urls)+'</urlset>'
    return body,200,{'Content-Type':'application/xml; charset=utf-8'}

# ============================================================
# PRODUCT DETAIL
# ============================================================

@app.route(
    "/product/<int:product_id>"
)
def product_detail(
    product_id
):

    product = get_normalized_product(
        product_id
    )


    if not product:

        flash(
            "محصول موردنظر پیدا نشد.",
            "error",
        )

        return redirect(
            url_for(
                "products_page"
            )
        )


    site = (
        get_site_settings()
        or default_site()
    )

    logo = (
        get_logo()
        or {
            "filename": "logo/logo.png"
        }
    )

    reviews = get_product_reviews(
        product_id,
        approved_only=True,
    ) or []


    return render_template(

        "product_detail.html",

        product=product,

        site=site,

        logo=logo,

        reviews=reviews,

    )


# ============================================================
# PRODUCTS PAGE
# ============================================================

@app.route("/products/category/<path:category_name>")
def category_products_page(category_name):
    return products_page(category_name)


@app.route("/pages/products.html")
def products_page(category_name=None):
    site = get_site_settings() or default_site()
    products = get_all_normalized_products()
    categories = get_categories() or []
    category = (category_name or request.args.get("category") or "").strip()
    filter_type = (request.args.get("filter") or "").strip().lower()
    search_query = (request.args.get("q") or "").strip()
    if search_query:
        q=search_query.casefold()
        products=[p for p in products if q in (p.get("title") or "").casefold() or q in (p.get("description") or "").casefold() or q in (p.get("tags") or "").casefold() or q in (p.get("category_name") or "").casefold()]
    if category:
        products = [p for p in products if (p.get("category_name") or "").strip().casefold() == category.casefold()]
    elif filter_type == "discount":
        products = [p for p in products if p.get("is_discount")]
    elif filter_type == "popular":
        products = [p for p in products if p.get("is_popular")]
    grouped_products = {}
    for product in products:
        grouped_products.setdefault(product.get("category_name") or "سایر محصولات", []).append(product)
    banners = [b for b in (get_banners() or []) if b.get("is_active", 1)][:5]
    selected_category_obj = next((c for c in categories if (c.get("name") or "").casefold() == category.casefold()), None) if category else None
    logo = get_logo() or {"filename": "logo/logo.png"}
    return render_template("products.html", site=site, products=products, grouped_products=grouped_products, categories=categories, banners=banners, logo=logo, selected_category=category, selected_category_obj=selected_category_obj, filter_type=filter_type, search_query=search_query)



# ============================================================
# PUBLIC PROFILES / KNOWLEDGE
# ============================================================

def _public_slug(value):
    value = (value or '').strip().lower()
    value = value.replace('ي','ی').replace('ك','ک')
    value = re.sub(r'[^\w\u0600-\u06ff-]+', '-', value, flags=re.UNICODE)
    value = re.sub(r'-{2,}', '-', value).strip('-_')
    return value[:120]


def _unique_slug(base, getter, current_id=None):
    slug = _public_slug(base) or secrets.token_hex(4)
    candidate = slug
    n = 2
    while True:
        row = getter(candidate)
        if not row or (current_id is not None and int(row.get('id', 0)) == int(current_id)):
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


def _json_list(raw):
    try:
        value = json.loads(raw or '[]')
        return value if isinstance(value, list) else []
    except Exception:
        return []


@app.route('/pages/profiles.html')
def profiles_page():
    site = get_site_settings() or default_site()
    categories = get_profile_categories()
    profiles = get_profiles(published_only=True)
    grouped = {}
    for profile in profiles:
        grouped.setdefault(profile.get('category_name') or 'سایر', []).append(profile)
    return render_template('profiles.html', site=site, logo=get_logo() or {'filename':'logo/logo.png'}, categories=categories, profiles=profiles, grouped_profiles=grouped)


@app.route('/profile/<slug>')
def public_profile_detail(slug):
    profile = get_profile_by_slug(slug, published_only=True)
    if not profile:
        return render_template('404.html'), 404
    profile['gallery'] = _json_list(profile.get('gallery_json'))
    profile['facts'] = _json_list(profile.get('facts_json'))
    site = get_site_settings() or default_site()
    return render_template('profile_detail.html', site=site, logo=get_logo() or {'filename':'logo/logo.png'}, profile=profile)


@app.route('/profile/<slug>/image')
def download_profile_image(slug):
    profile = get_profile_by_slug(slug, published_only=True)
    if not profile or not profile.get('image'):
        return ('تصویر پیدا نشد', 404)
    return send_from_directory(str(PROFILE_IMAGES_DIR), profile['image'], as_attachment=True, download_name=f"{_public_slug(profile['title']) or 'profile'}{Path(profile['image']).suffix.lower() or '.jpg'}")


@app.route('/pages/knowledge.html')
def knowledge_page():
    site = get_site_settings() or default_site()
    articles = get_knowledge_articles(published_only=True)
    categories = sorted({a.get('category') for a in articles if a.get('category')})
    return render_template('knowledge.html', site=site, logo=get_logo() or {'filename':'logo/logo.png'}, articles=articles, categories=categories)


@app.route('/knowledge/<slug>')
def knowledge_detail(slug):
    article = get_knowledge_article_by_slug(slug, published_only=True)
    if not article:
        return render_template('404.html'), 404
    site = get_site_settings() or default_site()
    return render_template('knowledge_detail.html', site=site, logo=get_logo() or {'filename':'logo/logo.png'}, article=article)


# ============================================================
# PUBLIC USER PROFILE (TAW-BIO STYLE)
# ============================================================
@app.route("/u/add", methods=["GET","POST"])
def public_profile_add():
    if not session.get("user_id"):
        return redirect(url_for("account", next="/u/add"))
    user=get_user_by_id(session["user_id"])
    existing=get_public_profile_for_user(session["user_id"])
    if request.method=="POST":
        username=_slug_username(request.form.get("username"))
        display=(request.form.get("display_name") or "").strip()[:100]
        bio=sanitize_rich_html(request.form.get("bio_html") or "")
        if not username or len(username)<3 or not display:
            flash("نام کاربری حداقل ۳ نویسه و نام نمایشی الزامی است.","error")
            return render_template("public_profile_add.html",profile=existing,user=user)
        conn=sqlite3.connect(str(BASE_DIR/"honeyshop.db"))
        try:
            duplicate=conn.execute("SELECT id FROM public_profiles WHERE username=? AND user_id<>?",(username,session["user_id"])).fetchone()
            if duplicate:
                flash("این نام کاربری قبلاً استفاده شده است.","error")
                return render_template("public_profile_add.html",profile=existing,user=user)
            avatar=existing.get("avatar","") if existing else ""
            f=request.files.get("avatar")
            saved=save_uploaded_file(f, PROFILES_DIR, ALLOWED_IMAGE_EXTENSIONS)
            if saved: avatar=saved
            links=[{"title":t.strip(),"url":u.strip()} for t,u in zip(request.form.getlist("link_title"),request.form.getlist("link_url")) if t.strip() and u.strip()]
            if existing:
                conn.execute("""UPDATE public_profiles SET username=?,display_name=?,bio_html=?,avatar=?,links_json=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?""",
                             (username,display,bio,avatar,json.dumps(links,ensure_ascii=False),session["user_id"]))
            else:
                conn.execute("""INSERT INTO public_profiles(user_id,username,display_name,bio_html,avatar,links_json) VALUES(?,?,?,?,?,?)""",
                             (session["user_id"],username,display,bio,avatar,json.dumps(links,ensure_ascii=False)))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("اطلاعات پروفایل تکراری است.","error"); return render_template("public_profile_add.html",profile=existing,user=user)
        finally: conn.close()
        flash("پروفایل شما ذخیره شد.","success")
        return redirect(url_for("public_profile",username=username))
    if existing:
        try: existing["links"]=json.loads(existing.get("links_json") or "[]")
        except Exception: existing["links"]=[]
    return render_template("public_profile_add.html",profile=existing,user=user)

@app.route("/u/<username>")
def public_profile(username):
    profile=get_public_profile(username)
    if not profile:return ("پروفایل پیدا نشد.",404)
    try: profile["links"]=json.loads(profile.get("links_json") or "[]")
    except Exception: profile["links"]=[]
    return render_template("public_profile.html",profile=profile,site=get_site_settings() or default_site(),logo=get_logo() or {"filename":"logo/logo.png"})

# ============================================================
# OWNER: PROFILES
# ============================================================

@app.route('/owner/profiles')
def manage_profiles():
    guard = owner_required()
    if guard: return guard
    return render_template('manage_profiles.html', profiles=get_profiles(), categories=get_profile_categories())


@app.route('/owner/profiles/add', methods=['GET','POST'])
def add_profile_page():
    guard = owner_required()
    if guard: return guard
    categories = get_profile_categories()
    if request.method == 'POST':
        title=(request.form.get('title') or '').strip()
        if not title:
            flash('عنوان پروفایل را وارد کنید.', 'error')
            return render_template('profile_editor.html', profile=None, categories=categories)
        slug=_unique_slug(request.form.get('slug') or title, lambda x:get_profile_by_slug(x, published_only=False))
        image=save_uploaded_file(request.files.get('image'), PROFILE_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS) or ''
        gallery=[]
        for f in request.files.getlist('gallery'):
            saved=save_uploaded_file(f, PROFILE_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS)
            if saved: gallery.append(saved)
        facts=[]
        for name,value in zip(request.form.getlist('fact_name'),request.form.getlist('fact_value')):
            if (name or '').strip() and (value or '').strip(): facts.append({'name':name.strip(),'value':value.strip()})
        data={'title':title,'slug':slug,'category_id':request.form.get('category_id',type=int),'subtitle':(request.form.get('subtitle') or '').strip(),'summary':(request.form.get('summary') or '').strip(),'content_html':sanitize_rich_html(request.form.get('content_html') or ''),'image':image,'gallery_json':json.dumps(gallery,ensure_ascii=False),'facts_json':json.dumps(facts,ensure_ascii=False),'seo_title':(request.form.get('seo_title') or '').strip(),'seo_description':(request.form.get('seo_description') or '').strip(),'is_published':request.form.get('is_published')=='1','sort_order':request.form.get('sort_order',type=int) or 0}
        try:
            create_profile(data); flash('پروفایل با موفقیت ساخته شد.', 'success'); return redirect(url_for('manage_profiles'))
        except sqlite3.IntegrityError:
            flash('اسلاگ پروفایل تکراری است.', 'error')
    return render_template('profile_editor.html', profile=None, categories=categories)


@app.route('/owner/profiles/<int:profile_id>/edit', methods=['GET','POST'])
def edit_profile_page(profile_id):
    guard=owner_required()
    if guard:return guard
    profile=get_profile(profile_id)
    if not profile:return redirect(url_for('manage_profiles'))
    categories=get_profile_categories()
    if request.method=='POST':
        title=(request.form.get('title') or '').strip()
        slug=_unique_slug(request.form.get('slug') or title, lambda x:get_profile_by_slug(x, published_only=False), profile_id)
        old_image=profile.get('image') or ''
        image=old_image
        new_image=save_uploaded_file(request.files.get('image'), PROFILE_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS)
        if new_image:
            image=new_image
            if old_image and old_image != new_image: delete_file_if_exists(PROFILE_IMAGES_DIR, old_image)
        gallery=_json_list(profile.get('gallery_json'))
        for f in request.files.getlist('gallery'):
            saved=save_uploaded_file(f, PROFILE_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS)
            if saved:gallery.append(saved)
        remove_gallery=set(request.form.getlist('remove_gallery'))
        gallery=[x for x in gallery if x not in remove_gallery]
        facts=[]
        for name,value in zip(request.form.getlist('fact_name'),request.form.getlist('fact_value')):
            if (name or '').strip() and (value or '').strip():facts.append({'name':name.strip(),'value':value.strip()})
        data={'title':title,'slug':slug,'category_id':request.form.get('category_id',type=int),'subtitle':(request.form.get('subtitle') or '').strip(),'summary':(request.form.get('summary') or '').strip(),'content_html':sanitize_rich_html(request.form.get('content_html') or ''),'image':image,'gallery_json':json.dumps(gallery,ensure_ascii=False),'facts_json':json.dumps(facts,ensure_ascii=False),'seo_title':(request.form.get('seo_title') or '').strip(),'seo_description':(request.form.get('seo_description') or '').strip(),'is_published':request.form.get('is_published')=='1','sort_order':request.form.get('sort_order',type=int) or 0}
        try:
            update_profile(profile_id,data);flash('پروفایل به‌روزرسانی شد.','success');return redirect(url_for('manage_profiles'))
        except sqlite3.IntegrityError:flash('اسلاگ پروفایل تکراری است.','error')
    profile['gallery']=_json_list(profile.get('gallery_json'));profile['facts']=_json_list(profile.get('facts_json'))
    return render_template('profile_editor.html',profile=profile,categories=categories)


@app.route('/owner/profiles/<int:profile_id>/delete',methods=['POST'])
def delete_profile_page(profile_id):
    guard=owner_required()
    if guard:return guard
    profile=get_profile(profile_id)
    if profile:
        for filename in [profile.get('image')]+_json_list(profile.get('gallery_json')):
            if filename:delete_file_if_exists(PROFILE_IMAGES_DIR,filename)
        delete_profile(profile_id);flash('پروفایل حذف شد.','success')
    return redirect(url_for('manage_profiles'))


@app.route('/owner/profile-categories/add',methods=['POST'])
def add_profile_category_page():
    guard=owner_required()
    if guard:return guard
    name=(request.form.get('name') or '').strip()
    if name:
        slug=_unique_slug(request.form.get('slug') or name, lambda x: next((c for c in get_profile_categories() if c.get('slug')==x),None))
        try:create_profile_category(name,slug);flash('دسته پروفایل اضافه شد.','success')
        except sqlite3.IntegrityError:flash('این دسته قبلاً وجود دارد.','error')
    return redirect(url_for('manage_profiles'))


@app.route('/owner/profiles/editor/image',methods=['POST'])
def upload_profile_editor_image():
    guard=owner_required()
    if guard:return guard
    filename=save_uploaded_file(request.files.get('image'), PROFILE_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS)
    if not filename:return jsonify({'success':False,'message':'تصویر معتبر نیست یا حجم آن زیاد است.'}),400
    return jsonify({'success':True,'url':url_for('uploads',filename='profile_knowledge/'+filename)})


# ============================================================
# OWNER: KNOWLEDGE
# ============================================================

@app.route('/owner/knowledge')
def manage_knowledge():
    guard=owner_required()
    if guard:return guard
    return render_template('manage_knowledge.html',articles=get_knowledge_articles())


@app.route('/owner/knowledge/add',methods=['GET','POST'])
def add_knowledge_page():
    guard=owner_required()
    if guard:return guard
    if request.method=='POST':
        title=(request.form.get('title') or '').strip()
        if not title:
            flash('عنوان مقاله را وارد کنید.','error');return render_template('knowledge_editor.html',article=None)
        slug=_unique_slug(request.form.get('slug') or title,lambda x:get_knowledge_article_by_slug(x,False))
        cover=save_uploaded_file(request.files.get('cover_image'),KNOWLEDGE_IMAGES_DIR,ALLOWED_IMAGE_EXTENSIONS) or ''
        data={'title':title,'slug':slug,'category':(request.form.get('category') or '').strip(),'excerpt':(request.form.get('excerpt') or '').strip(),'content_html':sanitize_rich_html(request.form.get('content_html') or ''),'cover_image':cover,'seo_title':(request.form.get('seo_title') or '').strip(),'seo_description':(request.form.get('seo_description') or '').strip(),'is_published':request.form.get('is_published')=='1'}
        try:create_knowledge_article(data);flash('مقاله با موفقیت ساخته شد.','success');return redirect(url_for('manage_knowledge'))
        except sqlite3.IntegrityError:flash('اسلاگ مقاله تکراری است.','error')
    return render_template('knowledge_editor.html',article=None)


@app.route('/owner/knowledge/<int:article_id>/edit',methods=['GET','POST'])
def edit_knowledge_page(article_id):
    guard=owner_required()
    if guard:return guard
    article=get_knowledge_article(article_id)
    if not article:return redirect(url_for('manage_knowledge'))
    if request.method=='POST':
        title=(request.form.get('title') or '').strip();slug=_unique_slug(request.form.get('slug') or title,lambda x:get_knowledge_article_by_slug(x,False),article_id)
        old_cover=article.get('cover_image') or ''
        cover=old_cover
        new_cover=save_uploaded_file(request.files.get('cover_image'),KNOWLEDGE_IMAGES_DIR,ALLOWED_IMAGE_EXTENSIONS)
        if new_cover:
            cover=new_cover
            if old_cover and old_cover != new_cover: delete_file_if_exists(KNOWLEDGE_IMAGES_DIR, old_cover)
        data={'title':title,'slug':slug,'category':(request.form.get('category') or '').strip(),'excerpt':(request.form.get('excerpt') or '').strip(),'content_html':sanitize_rich_html(request.form.get('content_html') or ''),'cover_image':cover,'seo_title':(request.form.get('seo_title') or '').strip(),'seo_description':(request.form.get('seo_description') or '').strip(),'is_published':request.form.get('is_published')=='1'}
        try:update_knowledge_article(article_id,data);flash('مقاله به‌روزرسانی شد.','success');return redirect(url_for('manage_knowledge'))
        except sqlite3.IntegrityError:flash('اسلاگ مقاله تکراری است.','error')
    return render_template('knowledge_editor.html',article=article)


@app.route('/owner/knowledge/<int:article_id>/delete',methods=['POST'])
def delete_knowledge_page(article_id):
    guard=owner_required()
    if guard:return guard
    article=get_knowledge_article(article_id)
    if article and article.get('cover_image'):delete_file_if_exists(KNOWLEDGE_IMAGES_DIR,article['cover_image'])
    if delete_knowledge_article(article_id):flash('مقاله حذف شد.','success')
    return redirect(url_for('manage_knowledge'))


@app.route('/owner/knowledge/editor/image',methods=['POST'])
def upload_knowledge_editor_image():
    guard=owner_required()
    if guard:return guard
    filename=save_uploaded_file(request.files.get('image'),KNOWLEDGE_IMAGES_DIR,ALLOWED_IMAGE_EXTENSIONS)
    if not filename:return jsonify({'success':False,'message':'تصویر معتبر نیست یا حجم آن زیاد است.'}),400
    return jsonify({'success':True,'url':url_for('uploads',filename='knowledge/'+filename)})


# ============================================================
# SIMPLE PAGES
# ============================================================

@app.route("/pages/about.html")
def about_page():
    site = get_site_settings() or default_site()
    return render_template("site_page.html", site=site, logo=get_logo() or {"filename":"logo/logo.png"}, page_icon="🍯", page_title=site.get("about_title") or "درباره شهدآور", page_text=sanitize_rich_html(site.get("about_text") or "<p>شهدآور با هدف عرضه محصولات طبیعی و اصیل زنبورداری فعالیت می‌کند.</p>"), page_image=site.get("about_image") or "", page_link=site.get("about_link") or "")


@app.route("/owner/about/image", methods=["POST"])
def upload_about_editor_image():
    guard = owner_required()
    if guard: return guard
    filename = save_uploaded_file(request.files.get("image"), ABOUT_IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS)
    if not filename:
        return jsonify({"success": False, "message": "تصویر معتبر نیست یا حجم آن بیش از حد مجاز است."}), 400
    return jsonify({"success": True, "url": url_for("uploads", filename="about/" + filename)})


@app.route("/pages/support.html")
def support_page():
    if not session.get("user_id"):
        flash("برای ورود به گفت‌وگوی آنلاین ابتدا وارد حساب کاربری خود شوید.", "error")
        return redirect(url_for("account"))
    site = get_site_settings() or default_site()
    return render_template("support.html", site=site, logo=get_logo() or {"filename":"logo/logo.png"}, support_text=site.get("support_text") or "پشتیبانی آنلاین شهدآور آماده پاسخ‌گویی به شماست.", support_branding=_support_branding())


# ============================================================
# CONTACT DATA API (static fallback / integrations)
# ============================================================

@app.route("/api/contact", methods=["GET"])
def contact_data_api():
    site = get_site_settings() or default_site()
    methods = get_normalized_contact_methods(active_only=True)
    return jsonify({
        "success": True,
        "title": site.get("contact_title") or "تماس با شهدآور",
        "text": site.get("contact_text") or "",
        "button_text": site.get("contact_button_text") or "ارتباط",
        "methods": methods,
    })


# ============================================================
# CONTACT PUBLIC PAGE
# ============================================================

@app.route(
    "/pages/contact.html"
)
def contact_page():

    site = (
        get_site_settings()
        or default_site()
    )


    contact_methods = (
        get_normalized_contact_methods(
            active_only=True
        )
    )


    logo = (
        get_logo()
        or {
            "filename":
                "logo/logo.png"
        }
    )


    return render_template(

        "contact.html",

        site=site,

        logo=logo,

        contact_methods=contact_methods,

        # برای قالب‌هایی که از contacts استفاده می‌کنند
        contacts=contact_methods,

        page_title=(
            site.get(
                "contact_title"
            )
            or "تماس با شهدآور"
        ),

    )


# ============================================================
# SHAH DYAR PAGE
# ============================================================

@app.route(
    "/pages/ai.html"
)
def ai_page():

    # --------------------------------------------------------
    # احراز هویت اجباری
    # --------------------------------------------------------

    if not shahdyar_authenticated():

        flash(
            "برای استفاده از شهدیار ابتدا وارد حساب کاربری خود شوید.",
            "error",
        )

        return redirect(
            url_for(
                "account"
            )
        )


    site = (
        get_site_settings()
        or default_site()
    )


    logo = (
        get_logo()
        or {
            "filename":
                "logo/logo.png"
        }
    )


    return render_template(

        "ai.html",

        site=site,

        logo=logo,

    )


# ============================================================
# SHAH DYAR CHAT API
# ============================================================

@app.route(
    "/api/ai/chat",
    methods=["POST"],
)
def shahdyar_chat():

    # --------------------------------------------------------
    # AUTH
    # --------------------------------------------------------

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    user_id = get_shahdyar_user_id()


    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    message = (
        data.get(
            "message"
        )
        or ""
    ).strip()


    if not message:

        return jsonify({

            "success":
                False,

            "message":
                "لطفاً پیام خود را وارد کنید.",

        }), 400


    # --------------------------------------------------------
    # MAX SINGLE MESSAGE LENGTH
    # --------------------------------------------------------

    if len(message) > 8000:

        return jsonify({

            "success":
                False,

            "message":
                (
                    "پیام شما بیش از حد طولانی است. "
                    "لطفاً پیام را کوتاه‌تر کنید."
                ),

        }), 400


    # --------------------------------------------------------
    # GET CURRENT CHAT
    # --------------------------------------------------------

    chat_id = session.get(
        "shahdyar_chat_id"
    )

    chat = None


    if chat_id:

        try:

            chat = get_chat_session(
                chat_id,
                user_id,
            )

        except Exception as error:

            app.logger.exception(
                "Shahdyar session lookup error: %s",
                error,
            )

            chat = None


    # --------------------------------------------------------
    # CREATE NEW CHAT IF NEEDED
    # --------------------------------------------------------

    if not chat:

        try:

            chat = create_chat_session(
                user_id
            )

        except Exception as error:

            app.logger.exception(
                "Shahdyar session creation error: %s",
                error,
            )

            return jsonify({

                "success":
                    False,

                "message":
                    (
                        "ایجاد گفت‌وگوی شهدیار "
                        "با مشکل مواجه شد."
                    ),

            }), 500


        chat_id = chat["chat_id"]

        session["shahdyar_chat_id"] = chat_id

        session.modified = True


    # --------------------------------------------------------
    # MESSAGE LIMIT
    # --------------------------------------------------------

    try:

        allowed = can_send_message(
            chat
        )

    except Exception as error:

        app.logger.exception(
            "Shahdyar limit check error: %s",
            error,
        )

        return jsonify({

            "success":
                False,

            "message":
                "بررسی وضعیت گفت‌وگو انجام نشد.",

        }), 500


    if not allowed:

        status = get_chat_status(
            chat
        )

        return jsonify({

            "success":
                False,

            "limit_reached":
                True,

            "message":
                (
                    "سقف ۱۰ پیام این گفت‌وگو "
                    "به پایان رسیده است. "
                    "برای ادامه یک گفت‌وگوی جدید شروع کنید."
                ),

            "chat":
                status,

        }), 429


    # --------------------------------------------------------
    # GENERATE RESPONSE
    # --------------------------------------------------------

    try:

        answer = generate_ai_response(
            app,
            chat,
            message,
        )

    except Exception as error:

        app.logger.exception(
            "Shahdyar AI error: %s",
            error,
        )

        return jsonify({

            "success":
                False,

            "message":
                (
                    "متأسفانه در ارتباط با "
                    "دستیار هوشمند مشکلی پیش آمد. "
                    "لطفاً دوباره تلاش کنید."
                ),

        }), 500


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = get_chat_status(
        chat
    )


    try:

        message_count = len(
            get_messages(
                chat
            )
        )

    except Exception:

        message_count = 0


    return jsonify({

        "success":
            True,

        "answer":
            answer,

        "chat_id":
            chat_id,

        "status":
            status,

        "messages":
            message_count,

    }), 200


# ============================================================
# NEW SHAH DYAR CHAT
# ============================================================

@app.route(
    "/api/ai/chat/new",
    methods=["POST"],
)
def shahdyar_new_chat():

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    user_id = get_shahdyar_user_id()


    # --------------------------------------------------------
    # DELETE PREVIOUS TEMPORARY CHAT
    # --------------------------------------------------------

    old_chat_id = session.get(
        "shahdyar_chat_id"
    )


    if old_chat_id:

        try:

            delete_chat_session(
                old_chat_id,
                user_id,
            )

        except Exception as error:

            app.logger.warning(
                "Could not delete old Shahdyar chat: %s",
                error,
            )


    # --------------------------------------------------------
    # CREATE NEW CHAT
    # --------------------------------------------------------

    try:

        chat = create_chat_session(
            user_id
        )

    except Exception as error:

        app.logger.exception(
            "Shahdyar new chat error: %s",
            error,
        )

        return jsonify({

            "success":
                False,

            "message":
                "گفت‌وگوی جدید ایجاد نشد.",

        }), 500


    chat_id = chat[
        "chat_id"
    ]


    session["shahdyar_chat_id"] = (
        chat_id
    )

    session.modified = True


    return jsonify({

        "success":
            True,

        "message":
            "گفت‌وگوی جدید آماده است.",

        "chat_id":
            chat_id,

        "status":
            get_chat_status(
                chat
            ),

    }), 201


# ============================================================
# SHAH DYAR CHAT STATUS
# ============================================================

@app.route(
    "/api/ai/chat/status",
    methods=["GET"],
)
def shahdyar_chat_status():

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    user_id = get_shahdyar_user_id()

    chat_id = session.get(
        "shahdyar_chat_id"
    )


    if not chat_id:

        return jsonify({

            "success":
                True,

            "active":
                False,

            "chat":
                None,

        }), 200


    chat = get_chat_session(
        chat_id,
        user_id,
    )


    if not chat:

        session.pop(
            "shahdyar_chat_id",
            None,
        )

        session.modified = True


        return jsonify({

            "success":
                True,

            "active":
                False,

            "chat":
                None,

        }), 200


    return jsonify({

        "success":
            True,

        "active":
            True,

        "chat":
            get_chat_status(
                chat
            ),

    }), 200


# ============================================================
# DELETE SHAH DYAR CHAT
# ============================================================

@app.route(
    "/api/ai/chat",
    methods=["DELETE"],
)
def shahdyar_delete_chat():

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    user_id = get_shahdyar_user_id()

    chat_id = session.get(
        "shahdyar_chat_id"
    )


    if chat_id:

        try:

            delete_chat_session(
                chat_id,
                user_id,
            )

        except Exception as error:

            app.logger.warning(
                "Shahdyar chat deletion error: %s",
                error,
            )


    session.pop(
        "shahdyar_chat_id",
        None,
    )

    session.modified = True


    return jsonify({

        "success":
            True,

        "message":
            "گفت‌وگوی شهدیار حذف شد.",

    }), 200


# ============================================================
# CLOSE SHAH DYAR CHAT
# ============================================================

@app.route(
    "/api/ai/chat/close",
    methods=["POST"],
)
def shahdyar_close_chat():

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    user_id = get_shahdyar_user_id()

    chat_id = session.get(
        "shahdyar_chat_id"
    )


    if chat_id:

        try:

            delete_chat_session(
                chat_id,
                user_id,
            )

        except Exception as error:

            app.logger.warning(
                "Shahdyar close chat error: %s",
                error,
            )


    session.pop(
        "shahdyar_chat_id",
        None,
    )

    session.modified = True


    return jsonify({

        "success":
            True,

    }), 200


# ============================================================
# SHAH DYAR PROVIDER STATUS
# ============================================================

@app.route(
    "/api/ai/provider-status",
    methods=["GET"],
)
def shahdyar_provider_status():

    auth_error = (
        shahdyar_auth_required()
    )

    if auth_error:

        return auth_error


    try:

        status = get_provider_status()

    except Exception as error:

        app.logger.exception(
            "Shahdyar provider status error: %s",
            error,
        )

        return jsonify({

            "success":
                False,

            "message":
                "وضعیت سرویس‌ها قابل دریافت نیست.",

        }), 500


    return jsonify({

        "success":
            True,

        "providers":
            status,

    }), 200


# ============================================================
# FAQ
# ============================================================

@app.route(
    "/pages/faq.html"
)
def faq_page():

    return redirect(
        url_for(
            "home"
        )
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()

    print(
        "===================================="
    )

    print(
        "🍯 HoneyShop"
    )

    print(
        "🤖 Shahdyar AI"
    )

    print(
        "📞 Dynamic Contact System"
    )

    print(
        "🔥 Flask Server"
    )

    print(
        "===================================="
    )

    print()

    print(
        "Website:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print()

    print(
        "Owner Panel:"
    )

    print(
        "http://127.0.0.1:5000/owner"
    )

    print()

    print(
        "Contact Management:"
    )

    print(
        "http://127.0.0.1:5000/owner/contact"
    )

    print()

    print(
        "Contact Page:"
    )

    print(
        "http://127.0.0.1:5000/pages/contact.html"
    )

    print()

    print(
        "Shahdyar:"
    )

    print(
        "http://127.0.0.1:5000/pages/ai.html"
    )

    print()

    print(
        "Owner Phone:"
    )

    print(
        OWNER_PHONE
    )

    print()

    print(
        "===================================="
    )

    print()


    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )