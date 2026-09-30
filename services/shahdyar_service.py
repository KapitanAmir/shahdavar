from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import requests


# ============================================================
# SHAHYAR AI
# شهدیار — دستیار هوشمند شهدآور
#
# معماری:
#
# 1. Site Knowledge Engine
# 2. Product Engine
# 3. Intent Engine
# 4. General Knowledge Layer
# 5. Conversation Memory
# 6. Provider Orchestrator
# 7. Validator
# 8. Response Composer
#
# اصل مهم:
#
# شهدیار فقط «ربات فروش محصول» نیست.
#
# او باید:
# - اطلاعات عمومی داشته باشد
# - اطلاعات واقعی سایت را بداند
# - اطلاعات عمومی را با اطلاعات واقعی سایت ترکیب کند
# - هیچ اطلاعات فروشگاهی را حدس نزند
# - محصولات جدید را خودکار ببیند
#
# Provider order:
# OpenRouter -> Cloudflare -> Aion Labs -> Cerebras
# ============================================================


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("shahdyar")

if not logger.handlers:
    handler = logging.StreamHandler()

    handler.setFormatter(
        logging.Formatter(
            "[SHAHDYAR] %(levelname)s: %(message)s"
        )
    )

    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# ============================================================
# CONSTANTS
# ============================================================

STORE_NAME = "شهدآور"

STORE_CREATOR = "رضا رحیمی"

STORE_LOCATION = (
    "استان لرستان، شهرستان بروجرد"
)

MAX_MESSAGES = 10
MAX_CONTEXT_MESSAGES = 14
SESSION_TTL_MINUTES = 30

HTTP_TIMEOUT = 30

MAX_SITE_FILE_CHARS = 12000
MAX_TOTAL_SITE_TEXT = 50000

PROVIDER_ORDER = (
    "openrouter",
    "cloudflare",
    "aionlabs",
    "cerebras",
)


# ============================================================
# ENV
# ============================================================

def env(*names: str) -> str:

    for name in names:

        value = os.getenv(name)

        if value:
            return value.strip()

    return ""

HTTP_TIMEOUT = int(env("SHAHDYAR_PROVIDER_TIMEOUT") or "30")


# ============================================================
# DATABASE PATH
# ============================================================

def _resolve_database_path(app=None) -> Path:
    """
    پیدا کردن دیتابیس واقعی شهدآور.

    اولویت:

    1. SHAHDYAR_DATABASE_PATH
    2. honeyshop.db داخل app.root_path
    3. honeyshop.db داخل cwd
    4. honeyshop.db داخل ریشه پروژه

    database.db فقط fallback قدیمی است.
    """

    configured = env(
        "SHAHDYAR_DATABASE_PATH"
    )

    if configured:

        return (
            Path(configured)
            .expanduser()
            .resolve()
        )

    candidates: list[Path] = []

    if app is not None:

        try:

            root = (
                Path(app.root_path)
                .resolve()
            )

            candidates.extend(
                [
                    root / "honeyshop.db",
                    root / "database.db",
                ]
            )

        except Exception:
            pass

    try:

        cwd = Path.cwd().resolve()

        candidates.extend(
            [
                cwd / "honeyshop.db",
                cwd / "database.db",
            ]
        )

    except Exception:
        pass

    try:

        root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        candidates.extend(
            [
                root / "honeyshop.db",
                root / "database.db",
            ]
        )

    except Exception:
        pass

    # همیشه honeyshop.db را ترجیح بده
    for path in candidates:

        if (
            path.name == "honeyshop.db"
            and path.exists()
        ):

            return path

    # fallback قدیمی
    for path in candidates:

        if path.exists():
            return path

    for path in candidates:

        if path.name == "honeyshop.db":
            return path

    return (
        Path.cwd()
        / "honeyshop.db"
    )


DATABASE_PATH = _resolve_database_path()

logger.info(
    "Shahdyar database: %s",
    DATABASE_PATH,
)


# ============================================================
# DATABASE
# ============================================================

def get_connection(app=None):

    path = _resolve_database_path(app)

    connection = sqlite3.connect(
        str(path),
        timeout=15,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# TEXT NORMALIZATION
# ============================================================

ARABIC_TO_PERSIAN = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
        "ٱ": "ا",
    }
)

PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789",
)

ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789",
)


def normalize_text(value: Any) -> str:

    if value is None:
        return ""

    text = str(value)

    text = text.translate(
        ARABIC_TO_PERSIAN
    )

    text = text.translate(
        PERSIAN_DIGITS
    )

    text = text.translate(
        ARABIC_DIGITS
    )

    text = text.replace(
        "\u200c",
        " "
    )

    text = text.replace(
        "\u200f",
        ""
    )

    text = text.replace(
        "\u200e",
        ""
    )

    text = text.replace(
        "ـ",
        ""
    )

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def compact_text(value: Any) -> str:

    return re.sub(
        r"[\s\-_،,؛;.!؟?:" + r"\"'()\[\]{}]+",
        "",
        normalize_text(value),
    )


def tokenize(value: Any) -> list[str]:

    return [
        token
        for token in normalize_text(value).split()
        if token
    ]


# ============================================================
# NUMBERS
# ============================================================

def parse_number(
    value: Any,
    default: float = 0,
) -> float:

    if value is None:
        return default

    text = normalize_text(value)

    text = (
        text
        .replace(",", "")
        .replace("٬", "")
        .replace("٫", ".")
        .replace("تومان", "")
        .replace("ریال", "")
        .strip()
    )

    try:
        return float(text)

    except Exception:
        return default


def format_price(value: Any) -> str:

    number = parse_number(
        value,
        0,
    )

    if number <= 0:
        return "قیمت نامشخص"

    if number.is_integer():
        number = int(number)

    return (
        f"{number:,}"
        .replace(",", "٬")
        + " تومان"
    )


# ============================================================
# PRODUCT ENGINE
# ============================================================

class ProductEngine:

    def __init__(
        self,
        app=None,
    ):

        self.app = app

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    @staticmethod
    def normalize_product(
        row,
    ) -> Optional[dict]:

        if not row:
            return None

        product = dict(row)

        for field in (
            "is_discount",
            "is_popular",
            "is_available",
        ):

            raw = product.get(
                field,
                0 if field != "is_available" else 1,
            )

            if isinstance(raw, bool):

                product[field] = raw

            elif str(raw).lower() in {
                "1",
                "true",
                "yes",
                "بله",
                "آری",
            }:

                product[field] = True

            else:

                product[field] = False

        return product

    # --------------------------------------------------------
    # All products
    # --------------------------------------------------------

    def get_all_products(self) -> list[dict]:

        connection = get_connection(
            self.app
        )

        try:

            rows = connection.execute(
                """
                SELECT
                    products.*,
                    categories.name AS category_name
                FROM products
                LEFT JOIN categories
                    ON products.category_id = categories.id
                ORDER BY products.id DESC
                """
            ).fetchall()

            return [
                self.normalize_product(row)
                for row in rows
                if row
            ]

        finally:

            connection.close()

    # --------------------------------------------------------
    # Available
    # --------------------------------------------------------

    def get_available_products(self) -> list[dict]:

        return [
            product
            for product in self.get_all_products()
            if self.is_available(product)
        ]

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------

    @staticmethod
    def is_available(
        product: dict,
    ) -> bool:

        status = normalize_text(
            product.get(
                "status",
                "",
            )
        )

        unavailable = {
            "unavailable",
            "ناموجود",
            "نا موجود",
            "اتمام موجودی",
            "تمام شده",
            "تمامشده",
            "غیرفعال",
            "غیر فعال",
            "out of stock",
        }

        if status in unavailable:
            return False

        raw = product.get(
            "is_available",
            1,
        )

        if raw is None:
            return True

        if isinstance(raw, bool):
            return raw

        value = normalize_text(raw)

        if value in {
            "0",
            "false",
            "no",
            "نه",
            "خیر",
        }:
            return False

        if value in {
            "1",
            "true",
            "yes",
            "بله",
            "آری",
        }:
            return True

        try:
            return bool(int(raw))

        except Exception:
            return bool(raw)

    # --------------------------------------------------------
    # Discount
    # --------------------------------------------------------

    @staticmethod
    def discount_not_expired(
        product: dict,
    ) -> bool:

        expires_at = product.get(
            "discount_expires_at"
        )

        if not expires_at:
            return True

        try:

            expires = datetime.fromisoformat(
                str(expires_at)
            )

            return datetime.now() <= expires

        except Exception:

            return True

    @classmethod
    def has_real_discount(
        cls,
        product: dict,
    ) -> bool:

        discount_flag = (
            bool(
                product.get(
                    "is_discount",
                    False,
                )
            )
            or
            normalize_text(
                product.get(
                    "status",
                    "",
                )
            ) == "discount"
            or
            parse_number(
                product.get(
                    "discount_percent"
                ),
                0,
            ) > 0
        )

        percent = parse_number(
            product.get(
                "discount_percent"
            ),
            0,
        )

        final_price = parse_number(
            product.get(
                "final_price"
            ),
            0,
        )

        base_price = parse_number(
            product.get(
                "price"
            ),
            0,
        )

        return (
            discount_flag
            and cls.discount_not_expired(product)
            and percent > 0
            and final_price > 0
            and base_price > final_price
        )

    # --------------------------------------------------------
    # Effective price
    # --------------------------------------------------------

    @classmethod
    def effective_price(
        cls,
        product: dict,
    ) -> float:

        if cls.has_real_discount(product):

            final_price = parse_number(
                product.get(
                    "final_price"
                ),
                0,
            )

            if final_price > 0:
                return final_price

        return parse_number(
            product.get(
                "price"
            ),
            0,
        )

    # --------------------------------------------------------
    # Product
    # --------------------------------------------------------

    def get_product(
        self,
        product_id: int,
    ) -> Optional[dict]:

        connection = get_connection(
            self.app
        )

        try:

            row = connection.execute(
                """
                SELECT
                    products.*,
                    categories.name AS category_name
                FROM products
                LEFT JOIN categories
                    ON products.category_id = categories.id
                WHERE products.id = ?
                LIMIT 1
                """,
                (product_id,),
            ).fetchone()

            return self.normalize_product(
                row
            )

        finally:

            connection.close()

    # --------------------------------------------------------
    # Search score
    # --------------------------------------------------------

    @staticmethod
    def score_product(
        query: str,
        product: dict,
    ) -> float:

        q = normalize_text(query)

        if not q:
            return 0

        title = normalize_text(
            product.get(
                "title",
                "",
            )
        )

        if not title:
            return 0

        qc = compact_text(q)
        tc = compact_text(title)

        if q == title:
            return 1.0

        if qc == tc:
            return 0.99

        if title in q:
            return 0.96

        if q in title:
            return 0.95

        q_tokens = set(
            tokenize(q)
        )

        t_tokens = set(
            tokenize(title)
        )

        overlap = 0

        if q_tokens and t_tokens:

            overlap = (
                len(q_tokens & t_tokens)
                /
                max(
                    len(q_tokens),
                    len(t_tokens),
                )
            )

        ratio = SequenceMatcher(
            None,
            qc,
            tc,
        ).ratio()

        return max(
            ratio,
            overlap * 0.92,
        )

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict]:

        query = normalize_text(query)

        if not query:
            return []

        results = []

        for product in self.get_all_products():

            score = self.score_product(
                query,
                product,
            )

            if score >= 0.48:

                results.append(
                    (
                        score,
                        product,
                    )
                )

        results.sort(
            key=lambda item: (
                item[0],
                item[1].get("id", 0),
            ),
            reverse=True,
        )

        return [
            item[1]
            for item in results[:limit]
        ]

    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    def get_categories(self) -> list[dict]:

        connection = get_connection(
            self.app
        )

        try:

            rows = connection.execute(
                """
                SELECT *
                FROM categories
                ORDER BY id ASC
                """
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            connection.close()

    def find_category(
        self,
        query: str,
    ) -> Optional[dict]:

        q = normalize_text(query)

        if not q:
            return None

        best = None
        best_score = 0

        for category in self.get_categories():

            name = normalize_text(
                category.get(
                    "name",
                    "",
                )
            )

            if not name:
                continue

            if q == name:
                return category

            if q in name or name in q:
                score = 0.92

            else:

                score = SequenceMatcher(
                    None,
                    compact_text(q),
                    compact_text(name),
                ).ratio()

            if score > best_score:

                best_score = score
                best = category

        if best_score >= 0.58:
            return best

        return None

    def products_by_category(
        self,
        category_name: str,
    ) -> list[dict]:

        category = self.find_category(
            category_name
        )

        if not category:
            return []

        connection = get_connection(
            self.app
        )

        try:

            rows = connection.execute(
                """
                SELECT
                    products.*,
                    categories.name AS category_name
                FROM products
                LEFT JOIN categories
                    ON products.category_id = categories.id
                WHERE products.category_id = ?
                ORDER BY products.id DESC
                """,
                (
                    category["id"],
                ),
            ).fetchall()

            return [
                self.normalize_product(row)
                for row in rows
                if row
            ]

        finally:

            connection.close()

    # --------------------------------------------------------
    # Product detail
    # --------------------------------------------------------

    def build_product_response(
        self,
        product: dict,
    ) -> str:

        title = (
            product.get("title")
            or "محصول"
        )

        lines = [
            f"🍯 {title}",
            "",
        ]

        if self.is_available(product):
            lines.append("✅ موجود")
        else:
            lines.append("❌ ناموجود")

        price = self.effective_price(
            product
        )

        if price > 0:

            lines.append(
                f"💰 قیمت: {format_price(price)}"
            )

        else:

            lines.append(
                "💰 قیمت: در حال حاضر ثبت نشده"
            )

        if self.has_real_discount(product):

            percent = int(
                parse_number(
                    product.get(
                        "discount_percent"
                    ),
                    0,
                )
            )

            lines.append(
                f"🏷️ تخفیف: {percent}٪"
            )

            old_price = parse_number(
                product.get("price"),
                0,
            )

            if old_price > 0:

                lines.append(
                    "💵 قیمت قبل از تخفیف: "
                    f"{format_price(old_price)}"
                )

        category = (
            product.get(
                "category_name"
            )
            or ""
        )

        if category:

            lines.append(
                f"📂 دسته‌بندی: {category}"
            )

        description = str(
            product.get(
                "description"
            )
            or ""
        ).strip()

        if description:

            lines.extend(
                [
                    "",
                    "📝 توضیحات:",
                    description,
                ]
            )

        return "\n".join(lines)

    # --------------------------------------------------------
    # Catalog
    # --------------------------------------------------------

    def build_catalog_response(
        self,
    ) -> str:

        products = self.get_all_products()

        if not products:

            return (
                f"🐝 فعلاً محصولی در {STORE_NAME} "
                "ثبت نشده است."
            )

        lines = [
            f"🍯 محصولات {STORE_NAME}:",
            "",
        ]

        for index, product in enumerate(
            products,
            start=1,
        ):

            title = (
                product.get("title")
                or "محصول"
            )

            price = self.effective_price(
                product
            )

            status = (
                "✅ موجود"
                if self.is_available(product)
                else "❌ ناموجود"
            )

            if price > 0:
                price_text = format_price(price)
            else:
                price_text = "قیمت ثبت نشده"

            lines.append(
                f"{index}. 🍯 {title}"
            )

            lines.append(
                f"   💰 {price_text} | {status}"
            )

            category = (
                product.get(
                    "category_name"
                )
                or ""
            )

            if category:

                lines.append(
                    f"   📂 {category}"
                )

            if self.has_real_discount(product):

                percent = int(
                    parse_number(
                        product.get(
                            "discount_percent"
                        ),
                        0,
                    )
                )

                lines.append(
                    f"   🏷️ تخفیف {percent}٪"
                )

            lines.append("")

        return "\n".join(lines).strip()


# ============================================================
# SITE KNOWLEDGE ENGINE
# ============================================================

class SiteKnowledge:

    """
    این بخش باعث می‌شود شهدیار فقط محصولات را نشناسد.

    اطلاعات را از:
    - site_settings
    - categories
    - products
    - covers
    - banners
    - logo
    - pages
    - templates
    می‌گیرد.

    بنابراین هرچه سایت بزرگ‌تر شود، context شهدیار هم
    می‌تواند بزرگ‌تر شود.
    """

    @staticmethod
    def _project_root(app=None) -> Path:

        if app is not None:

            try:
                return Path(
                    app.root_path
                ).resolve()

            except Exception:
                pass

        return (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

    # --------------------------------------------------------
    # Site settings
    # --------------------------------------------------------

    @classmethod
    def get_site_settings(
        cls,
        app=None,
    ) -> dict:
        """Read the real key-per-column site_settings schema used by HoneyShop."""
        connection = get_connection(app)
        try:
            row = connection.execute("SELECT * FROM site_settings ORDER BY id ASC LIMIT 1").fetchone()
            if not row:
                return {}
            data = dict(row)
            data.pop("id", None)
            return {k: v for k, v in data.items() if v is not None and str(v).strip()}
        except sqlite3.OperationalError:
            return {}
        finally:
            connection.close()

    # --------------------------------------------------------
    # Generic table reader
    # --------------------------------------------------------

    @classmethod
    def read_table(
        cls,
        table_name: str,
        app=None,
    ) -> list[dict]:

        connection = get_connection(
            app
        )

        try:

            try:

                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM {table_name}
                    LIMIT 200
                    """
                ).fetchall()

            except sqlite3.OperationalError:

                return []

            return [
                dict(row)
                for row in rows
            ]

        finally:

            connection.close()

    # --------------------------------------------------------
    # Extract visible text from HTML
    # --------------------------------------------------------

    @staticmethod
    def clean_html(
        html: str,
    ) -> str:

        html = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            html,
            flags=re.I | re.S,
        )

        html = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            html,
            flags=re.I | re.S,
        )

        html = re.sub(
            r"<[^>]+>",
            " ",
            html,
        )

        html = (
            html
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )

        html = re.sub(
            r"\s+",
            " ",
            html,
        )

        return html.strip()

    # --------------------------------------------------------
    # Read site files
    # --------------------------------------------------------

    @classmethod
    def read_site_files(
        cls,
        app=None,
    ) -> str:

        root = cls._project_root(app)

        directories = [
            root / "pages",
            root / "templates",
            root / "templates" / "pages",
        ]

        files: list[Path] = []

        for directory in directories:

            if not directory.exists():
                continue

            try:

                for file in directory.rglob("*.html"):

                    if file not in files:
                        files.append(file)

            except Exception:
                pass

        chunks = []
        total = 0

        for file in files:

            try:

                text = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

                text = cls.clean_html(
                    text
                )

                if not text:
                    continue

                text = text[
                    :MAX_SITE_FILE_CHARS
                ]

                chunk = (
                    f"\n--- صفحه سایت: "
                    f"{file.relative_to(root)} ---\n"
                    f"{text}"
                )

                if (
                    total + len(chunk)
                    >
                    MAX_TOTAL_SITE_TEXT
                ):
                    break

                chunks.append(chunk)

                total += len(chunk)

            except Exception:

                continue

        return "\n".join(chunks)

    # --------------------------------------------------------
    # Build complete site snapshot
    # --------------------------------------------------------

    @classmethod
    def build_snapshot(
        cls,
        app=None,
    ) -> str:

        engine = ProductEngine(
            app
        )

        parts = []

        # --------------------------------------------
        # Brand identity
        # --------------------------------------------

        parts.append(
            f"""
هویت برند:
نام سایت: {STORE_NAME}
سازنده و صاحب تجربه زنبورداری: {STORE_CREATOR}
موقعیت فعالیت: {STORE_LOCATION}

درباره سازنده:
رضا رحیمی یک زنبوردار با سابقه و با تجربه در پرورش
زنبور عسل و فرآورده‌های زنبور عسل در استان لرستان،
شهرستان بروجرد است.
""".strip()
        )

        # --------------------------------------------
        # Site settings
        # --------------------------------------------

        settings = cls.get_site_settings(
            app
        )

        if settings:

            lines = [
                "تنظیمات و اطلاعات ثبت‌شده سایت:"
            ]

            for key, value in settings.items():

                if value is None:
                    continue

                lines.append(
                    f"- {key}: {value}"
                )

            parts.append(
                "\n".join(lines)
            )

        # --------------------------------------------
        # Categories
        # --------------------------------------------

        categories = engine.get_categories()

        if categories:

            parts.append(
                "دسته‌بندی‌های واقعی سایت:\n"
                +
                "\n".join(
                    f"- {item.get('name', '')}"
                    for item in categories
                    if item.get("name")
                )
            )

        # --------------------------------------------
        # Products
        # --------------------------------------------

        products = engine.get_all_products()

        if products:

            lines = [
                "محصولات واقعی فعلی سایت:"
            ]

            for product in products:

                title = (
                    product.get("title")
                    or "محصول"
                )

                category = (
                    product.get(
                        "category_name"
                    )
                    or "بدون دسته‌بندی"
                )

                available = (
                    "موجود"
                    if engine.is_available(product)
                    else "ناموجود"
                )

                price = engine.effective_price(
                    product
                )

                if price > 0:
                    price_text = format_price(price)
                else:
                    price_text = "قیمت ثبت نشده"

                lines.append(
                    f"- {title}"
                )

                lines.append(
                    f"  دسته: {category}"
                )

                lines.append(
                    f"  وضعیت: {available}"
                )

                lines.append(
                    f"  قیمت واقعی ثبت‌شده: {price_text}"
                )

                description = (
                    product.get(
                        "description"
                    )
                    or ""
                ).strip()

                if description:

                    lines.append(
                        f"  توضیحات: {description}"
                    )

                if engine.has_real_discount(product):

                    percent = int(
                        parse_number(
                            product.get(
                                "discount_percent"
                            ),
                            0,
                        )
                    )

                    lines.append(
                        f"  تخفیف واقعی: {percent}٪"
                    )

            parts.append(
                "\n".join(lines)
            )

        # --------------------------------------------
        # Covers
        # --------------------------------------------

        covers = cls.read_table(
            "covers",
            app,
        )

        if covers:

            parts.append(
                "اطلاعات کاورهای سایت:\n"
                +
                json.dumps(
                    covers,
                    ensure_ascii=False,
                    default=str,
                )[:10000]
            )

        # --------------------------------------------
        # Banners
        # --------------------------------------------

        banners = cls.read_table(
            "banners",
            app,
        )

        if banners:

            parts.append(
                "اطلاعات بنرهای سایت:\n"
                +
                json.dumps(
                    banners,
                    ensure_ascii=False,
                    default=str,
                )[:10000]
            )

        # --------------------------------------------
        # Logo
        # --------------------------------------------

        logos = cls.read_table(
            "logo",
            app,
        )

        if logos:

            parts.append(
                "اطلاعات لوگوی سایت:\n"
                +
                json.dumps(
                    logos,
                    ensure_ascii=False,
                    default=str,
                )[:5000]
            )

        # --------------------------------------------
        # Actual site pages
        # --------------------------------------------

        site_files = cls.read_site_files(
            app
        )

        if site_files:

            parts.append(
                "متن و محتوای صفحات واقعی سایت:\n"
                + site_files
            )

        return "\n\n".join(
            parts
        )


# ============================================================
# GENERAL KNOWLEDGE
# ============================================================

class KnowledgeLayer:

    """
    دانش عمومی شهدیار.

    این دانش با اطلاعات سایت فرق دارد.

    هدف:
    - پاسخ عمومی
    - توضیح علمی و کاربردی
    - سپس اتصال به محصولات واقعی سایت
    """

    BASE = {

        "honey": """
عسل فرآورده‌ای طبیعی است که زنبور عسل از شهد گل‌ها تولید
می‌کند. ویژگی‌های عسل مانند رنگ، عطر، طعم و حتی سرعت
شکرک‌زدن می‌تواند با توجه به منبع گیاهی، منطقه، فصل و
شرایط تولید متفاوت باشد.

نگهداری عسل معمولاً در ظرف دربسته، محیط خشک و دور از
گرمای شدید و نور مستقیم انجام می‌شود.

شکرک‌زدن در بسیاری از عسل‌های طبیعی یک پدیده طبیعی است
و به‌تنهایی نشانه خراب بودن عسل نیست.
""",

        "sore_throat": """
برای گلودرد، عسل ممکن است برای بعضی افراد به تسکین موقت
تحریک گلو و سرفه کمک کند، اما نباید آن را درمان قطعی علت
گلودرد دانست.

عسل برای کودک زیر یک سال نباید مصرف شود.

اگر گلودرد شدید یا طولانی باشد یا با تب قابل توجه،
دشواری تنفس، دشواری بلع یا علائم نگران‌کننده همراه باشد،
بهتر است فرد توسط پزشک ارزیابی شود.
""",

        "cough": """
عسل ممکن است برای بعضی افراد به کاهش موقت سرفه کمک کند،
به‌خصوص وقتی گلو تحریک شده است؛ اما علت اصلی سرفه را
درمان نمی‌کند و جایگزین تشخیص پزشکی نیست.

برای کودک زیر یک سال عسل ممنوع است.
""",

        "royal_jelly": """
ژل رویال ماده‌ای طبیعی است که زنبورهای کارگر تولید می‌کنند
و در تغذیه لاروها و ملکه نقش دارد.

ژل رویال فرآورده‌ای متفاوت از عسل است و شرایط نگهداری و
مصرف آن باید بر اساس مشخصات همان محصول و دستور تولیدکننده
باشد.
""",

        "pollen": """
گرده گل توسط زنبورها جمع‌آوری می‌شود و می‌تواند از نظر
ترکیبات و ویژگی‌های ظاهری، بسته به منبع گیاهی متفاوت باشد.

برای مصرف و نگهداری گرده گل باید به مشخصات محصول مشخص و
دستور تولیدکننده توجه کرد.
""",

        "propolis": """
بره‌موم یا پروپولیس ماده‌ای رزینی است که زنبورها از منابع
گیاهی جمع‌آوری می‌کنند و در کندو از آن استفاده می‌کنند.

فرآورده‌های بره‌موم می‌توانند شکل و ترکیبات متفاوتی داشته
باشند و روش مصرف باید بر اساس محصول مشخص باشد.
""",

        "beekeeping": """
زنبورداری شامل مدیریت کلنی‌های زنبور عسل، بررسی سلامت
زنبورها، مدیریت ملکه، کنترل آفات و بیماری‌ها، تغذیه،
مدیریت کندو و برداشت و نگهداری محصولات زنبور عسل است.

کیفیت محصول زنبورداری به عوامل مختلفی مانند شرایط منطقه،
منبع گیاهی، زمان برداشت، مدیریت کلنی و فرآوری و نگهداری
وابسته است.
""",
    }

    # --------------------------------------------------------
    # Medical detection
    # --------------------------------------------------------

    @classmethod
    def is_medical(
        cls,
        query: str,
    ) -> bool:

        text = normalize_text(query)

        terms = (
            "درمان",
            "گلودرد",
            "گلو درد",
            "سرفه",
            "سرماخوردگی",
            "عفونت",
            "بیماری",
            "درد",
            "تب",
            "قند خون",
            "دیابت",
            "فشار خون",
            "دارو",
            "زخم",
            "حساسیت",
        )

        return any(
            term in text
            for term in terms
        )

    # --------------------------------------------------------
    # Sore throat
    # --------------------------------------------------------

    @classmethod
    def is_sore_throat(
        cls,
        query: str,
    ) -> bool:

        text = normalize_text(query)

        return (
            "گلودرد" in text
            or
            "گلو درد" in text
            or
            "گلو" in text
            and "درد" in text
        )

    # --------------------------------------------------------
    # Topic
    # --------------------------------------------------------

    @classmethod
    def detect_topic(
        cls,
        query: str,
    ) -> str:

        text = normalize_text(query)

        if cls.is_sore_throat(text):
            return "sore_throat"

        if "سرفه" in text:
            return "cough"

        if (
            "ژل رویال" in text
            or "ژل رو یال" in text
        ):
            return "royal_jelly"

        if (
            "گرده گل" in text
            or "گرده" in text
        ):
            return "pollen"

        if (
            "بره موم" in text
            or "بره‌موم" in text
            or "پروپولیس" in text
        ):
            return "propolis"

        if (
            "زنبورداری" in text
            or "زنبور" in text
            or "کندو" in text
        ):
            return "beekeeping"

        return "honey"

    # --------------------------------------------------------
    # General answer
    # --------------------------------------------------------

    @classmethod
    def answer(
        cls,
        query: str,
    ) -> str:

        topic = cls.detect_topic(
            query
        )

        return (
            cls.BASE.get(
                topic,
                cls.BASE["honey"],
            )
            .strip()
        )


# ============================================================
# INTENT ENGINE
# ============================================================

class IntentEngine:

    PRODUCT_LIST = (
        "چه محصولاتی",
        "چه محصول هایی",
        "چه چیزهایی دارید",
        "چه چیزایی دارید",
        "چی دارید",
        "چی میفروشید",
        "چی می فروشید",
        "چه میفروشید",
        "چه می فروشید",
        "لیست محصولات",
        "لیست محصول",
        "محصولاتتون",
        "محصولات شما",
        "محصولات شهدآور",
        "محصولات شهد اور",
        "محصولات دارید",
        "محصول دارید",
        "چه محصولی دارید",
    )

    PRICE = (
        "قیمت",
        "چنده",
        "چند است",
        "چند هست",
        "چقدر",
        "هزینه",
        "بها",
        "قیمتش",
    )

    AVAILABILITY = (
        "موجوده",
        "موجود هست",
        "موجود است",
        "موجود دارید",
        "موجودی",
        "دارید",
        "دارین",
        "ناموجود",
        "موجود نیست",
        "تمام شده",
        "تموم شده",
    )

    RECOMMENDATION = (
        "پیشنهاد",
        "پیشنهاد میکنی",
        "پیشنهاد میدی",
        "پیشنهاد بده",
        "پیشنهاد کن",
        "کدام",
        "کدوم",
        "بهترین",
        "چه عسلی",
        "چی بخورم",
        "چی استفاده کنم",
        "مناسب برای",
        "برای گلو",
        "برای گلودرد",
        "برای گلو درد",
    )

    CATEGORY = (
        "دسته بندی",
        "دسته‌بندی",
        "دسته ها",
        "دسته‌ها",
        "در دسته",
        "محصولات دسته",
    )

    GREETING = (
        "سلام",
        "درود",
        "وقت بخیر",
        "صبح بخیر",
        "عصر بخیر",
        "شب بخیر",
        "خسته نباشید",
    )

    ORDER = (
        "سفارش",
        "خرید",
        "پرداخت",
        "سبد خرید",
        "ارسال",
        "مرسوله",
        "پیگیری سفارش",
    )

    SUPPORT = (
        "پشتیبانی",
        "تماس",
        "ارتباط",
        "مشکل سایت",
        "مشکل دارم",
        "کمک",
        "راهنمایی",
    )

    @staticmethod
    def contains(
        text: str,
        patterns: tuple[str, ...],
    ) -> bool:

        text = normalize_text(text)

        return any(
            normalize_text(pattern)
            in text
            for pattern in patterns
        )

    # --------------------------------------------------------
    # Extract useful product phrase
    # --------------------------------------------------------

    @classmethod
    def extract_product_query(
        cls,
        text: str,
        engine: ProductEngine,
    ) -> tuple[str, Optional[int]]:

        normalized = normalize_text(
            text
        )

        matches = engine.search(
            normalized,
            limit=3,
        )

        if matches:

            best = matches[0]

            # Only accept fuzzy match when confidence
            # is genuinely good.
            score = engine.score_product(
                normalized,
                best,
            )

            if score >= 0.72:

                return (
                    best.get("title", ""),
                    best.get("id"),
                )

        return (
            normalized,
            None,
        )

    # --------------------------------------------------------
    # Category extraction
    # --------------------------------------------------------

    @classmethod
    def extract_category(
        cls,
        text: str,
    ) -> str:

        value = normalize_text(
            text
        )

        prefixes = (
            "محصولات دسته بندی",
            "محصولات دسته",
            "در دسته بندی",
            "در دسته",
        )

        for prefix in prefixes:

            prefix = normalize_text(
                prefix
            )

            if value.startswith(prefix):

                return value[
                    len(prefix):
                ].strip()

        return ""

    # --------------------------------------------------------
    # Classify
    # --------------------------------------------------------

    @classmethod
    def classify(
        cls,
        message: str,
        engine: ProductEngine,
    ) -> dict:

        text = normalize_text(
            message
        )

        if not text:

            return {
                "intent": "fallback",
                "query": "",
                "confidence": 0,
            }

        # --------------------------------------------
        # Greeting
        # --------------------------------------------

        if (
            cls.contains(
                text,
                cls.GREETING,
            )
            and len(text.split()) <= 8
        ):

            return {
                "intent": "greeting",
                "query": "",
                "confidence": 0.99,
            }

        # --------------------------------------------
        # Catalog
        # --------------------------------------------

        if cls.contains(
            text,
            cls.PRODUCT_LIST,
        ):

            return {
                "intent": "product_catalog",
                "query": "",
                "confidence": 0.99,
            }

        # --------------------------------------------
        # Category
        # --------------------------------------------

        if cls.contains(
            text,
            cls.CATEGORY,
        ):

            return {
                "intent": "category_browse",
                "query": cls.extract_category(text),
                "confidence": 0.94,
            }

        # --------------------------------------------
        # Medical recommendation
        # --------------------------------------------

        if (
            KnowledgeLayer.is_medical(text)
            and
            cls.contains(
                text,
                cls.RECOMMENDATION,
            )
        ):

            return {
                "intent": "knowledge_with_products",
                "query": text,
                "confidence": 0.98,
            }

        # --------------------------------------------
        # Medical/general knowledge
        # --------------------------------------------

        if KnowledgeLayer.is_medical(text):

            return {
                "intent": "knowledge_with_products",
                "query": text,
                "confidence": 0.96,
            }

        # --------------------------------------------
        # Recommendation
        # --------------------------------------------

        if cls.contains(
            text,
            cls.RECOMMENDATION,
        ):

            product_query, product_id = (
                cls.extract_product_query(
                    text,
                    engine,
                )
            )

            return {
                "intent": "recommendation",
                "query": product_query,
                "product_id": product_id,
                "confidence": 0.93,
            }

        # --------------------------------------------
        # Product exact/fuzzy
        # --------------------------------------------

        matches = engine.search(
            text,
            limit=3,
        )

        if matches:

            best = matches[0]

            score = engine.score_product(
                text,
                best,
            )

            if score >= 0.68:

                if cls.contains(
                    text,
                    cls.PRICE,
                ):

                    return {
                        "intent": "product_price",
                        "query": best["title"],
                        "product_id": best["id"],
                        "confidence": 0.97,
                    }

                if cls.contains(
                    text,
                    cls.AVAILABILITY,
                ):

                    return {
                        "intent": "product_availability",
                        "query": best["title"],
                        "product_id": best["id"],
                        "confidence": 0.97,
                    }

                return {
                    "intent": "product_detail",
                    "query": best["title"],
                    "product_id": best["id"],
                    "confidence": score,
                }

        # --------------------------------------------
        # Order
        # --------------------------------------------

        if cls.contains(
            text,
            cls.ORDER,
        ):

            return {
                "intent": "order_support",
                "query": text,
                "confidence": 0.86,
            }

        # --------------------------------------------
        # Support
        # --------------------------------------------

        if cls.contains(
            text,
            cls.SUPPORT,
        ):

            return {
                "intent": "support",
                "query": text,
                "confidence": 0.84,
            }

        # --------------------------------------------
        # General
        # --------------------------------------------

        return {
            "intent": "general",
            "query": text,
            "confidence": 0.40,
        }


# ============================================================
# RESPONSE COMPOSER
# ============================================================

class ResponseComposer:

    # --------------------------------------------------------
    # Brand intro
    # --------------------------------------------------------

    @staticmethod
    def brand_intro() -> str:

        return (
            "شهدآور با مدیریت و تجربه زنبورداری "
            "رضا رحیمی در استان لرستان، شهرستان بروجرد "
            "فعالیت می‌کنه؛ با تمرکز روی زنبور عسل و "
            "فرآورده‌های زنبور عسل."
        )

    # --------------------------------------------------------
    # Greeting
    # --------------------------------------------------------

    @classmethod
    def greeting(cls) -> str:

        return (
            "🐝 سلام رفیق! خوش اومدی به شهدآور 🍯\n\n"
            "من شهدیارم، دستیار هوشمند شهدآور. "
            "هم درباره عسل و دنیای زنبورداری اطلاعات دارم، "
            "هم می‌تونم درباره محصولات، قیمت، موجودی و "
            "بخش‌های مختلف خود شهدآور راهنماییت کنم.\n\n"
            "هر چیزی خواستی بپرس؛ از «چه عسلی برای گلودرد "
            "مناسبه؟» گرفته تا قیمت و مشخصات محصولات."
        )

    # --------------------------------------------------------
    # Medical + products
    # --------------------------------------------------------

    @classmethod
    def knowledge_with_products(
        cls,
        message: str,
        engine: ProductEngine,
    ) -> str:

        topic = KnowledgeLayer.detect_topic(
            message
        )

        knowledge = KnowledgeLayer.answer(
            message
        )

        available = (
            engine.get_available_products()
        )

        lines = [
            knowledge.strip(),
        ]

        # --------------------------------------------
        # Connect general knowledge to site
        # --------------------------------------------

        if available:

            relevant = []

            normalized = normalize_text(
                message
            )

            # First: products directly mentioned
            for product in available:

                title = normalize_text(
                    product.get("title", "")
                )

                if title and title in normalized:

                    relevant.append(product)

            # Second: honey products for honey/health questions
            if not relevant:

                for product in available:

                    title = normalize_text(
                        product.get("title", "")
                    )

                    category = normalize_text(
                        product.get(
                            "category_name",
                            "",
                        )
                    )

                    if (
                        "عسل" in title
                        or
                        "عسل" in category
                    ):

                        relevant.append(
                            product
                        )

            # Third: if no specific match, don't invent
            if relevant:

                # remove duplicates
                seen = set()
                unique = []

                for product in relevant:

                    pid = product.get("id")

                    if pid in seen:
                        continue

                    seen.add(pid)
                    unique.append(product)

                lines.extend(
                    [
                        "",
                        f"🍯 از محصولات موجود {STORE_NAME}، "
                        "این گزینه‌ها مرتبط‌تر هستند:",
                    ]
                )

                for product in unique[:5]:

                    title = (
                        product.get("title")
                        or "محصول"
                    )

                    price = engine.effective_price(
                        product
                    )

                    price_text = (
                        format_price(price)
                        if price > 0
                        else "قیمت ثبت نشده"
                    )

                    lines.append(
                        f"• {title} — "
                        f"{price_text} — "
                        "✅ موجود"
                    )

                lines.extend(
                    [
                        "",
                        "فقط یه نکته مهم: معرفی این محصولات "
                        "به معنی ادعای درمان قطعی نیست؛ "
                        "من صرفاً بر اساس اطلاعات عمومی و "
                        "محصولات واقعی موجود در شهدآور راهنماییت می‌کنم.",
                    ]
                )

            else:

                lines.extend(
                    [
                        "",
                        f"🍯 اگر دنبال محصول مرتبط از {STORE_NAME} "
                        "هستی، می‌تونم محصولات موجود فروشگاه "
                        "رو هم برات بررسی کنم.",
                    ]
                )

        else:

            lines.extend(
                [
                    "",
                    f"در حال حاضر محصول موجودی از {STORE_NAME} "
                    "برای معرفی پیدا نکردم.",
                ]
            )

        return "\n".join(lines).strip()

    # --------------------------------------------------------
    # Product detail
    # --------------------------------------------------------

    @staticmethod
    def product_detail(
        message: str,
        intent: dict,
        engine: ProductEngine,
    ) -> str:

        product = None

        if intent.get("product_id"):

            product = engine.get_product(
                intent["product_id"]
            )

        if not product:

            matches = engine.search(
                intent.get(
                    "query",
                    message,
                ),
                limit=1,
            )

            if matches:
                product = matches[0]

        if not product:

            return (
                "🐝 اسم این محصول رو در اطلاعات فعلی "
                f"{STORE_NAME} پیدا نکردم.\n\n"
                "اگه منظورت محصول دیگه‌ایه اسمش رو بگو. "
                "اگر هم درباره محصولی سؤال داری که هنوز "
                "اطلاعاتش روی سایت ثبت نشده، می‌تونی با "
                "پشتیبانی آنلاین شهدآور در ارتباط باشی."
            )

        return engine.build_product_response(
            product
        )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    @staticmethod
    def product_price(
        message: str,
        intent: dict,
        engine: ProductEngine,
    ) -> str:

        product = None

        if intent.get("product_id"):

            product = engine.get_product(
                intent["product_id"]
            )

        if not product:

            matches = engine.search(
                intent.get(
                    "query",
                    message,
                ),
                limit=1,
            )

            if matches:
                product = matches[0]

        if not product:

            return (
                "قیمت این محصول رو در اطلاعات فعلی "
                f"{STORE_NAME} پیدا نکردم.\n\n"
                "نمی‌خوام قیمت رو حدس بزنم؛ برای قیمت دقیق "
                "می‌تونی با پشتیبانی آنلاین شهدآور در ارتباط باشی."
            )

        title = (
            product.get("title")
            or "محصول"
        )

        price = engine.effective_price(
            product
        )

        if price <= 0:

            return (
                f"🍯 {title}\n\n"
                "قیمت این محصول در حال حاضر در اطلاعات "
                f"{STORE_NAME} ثبت نشده.\n\n"
                "برای قیمت دقیق می‌تونی با پشتیبانی آنلاین "
                "شهدآور در ارتباط باشی."
            )

        return (
            f"🍯 {title}\n"
            f"💰 قیمت فعلی: {format_price(price)}"
        )

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------

    @staticmethod
    def product_availability(
        message: str,
        intent: dict,
        engine: ProductEngine,
    ) -> str:

        product = None

        if intent.get("product_id"):

            product = engine.get_product(
                intent["product_id"]
            )

        if not product:

            matches = engine.search(
                intent.get(
                    "query",
                    message,
                ),
                limit=1,
            )

            if matches:
                product = matches[0]

        if not product:

            return (
                "اسم این محصول رو در اطلاعات فعلی "
                f"{STORE_NAME} پیدا نکردم؛ نمی‌خوام "
                "درباره موجودی حدس بزنم."
            )

        title = (
            product.get("title")
            or "محصول"
        )

        if engine.is_available(product):

            price = engine.effective_price(
                product
            )

            if price > 0:

                return (
                    f"🍯 {title}\n"
                    "✅ بله، در حال حاضر موجوده.\n"
                    f"💰 قیمت: {format_price(price)}"
                )

            return (
                f"🍯 {title}\n"
                "✅ بله، در حال حاضر موجوده.\n"
                "💰 قیمت در اطلاعات فعلی ثبت نشده."
            )

        return (
            f"🍯 {title}\n"
            "❌ در حال حاضر ناموجوده."
        )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    @classmethod
    def recommendation(
        cls,
        message: str,
        intent: dict,
        engine: ProductEngine,
    ) -> str:

        available = (
            engine.get_available_products()
        )

        if not available:

            return (
                f"🐝 فعلاً محصول موجودی برای پیشنهاد "
                f"از {STORE_NAME} پیدا نکردم.\n\n"
                "نمی‌خوام چیزی رو حدس بزنم. "
                "اگر خواستی می‌تونی با پشتیبانی آنلاین "
                "شهدآور در ارتباط باشی."
            )

        # ----------------------------------------------------
        # If specific product mentioned
        # ----------------------------------------------------

        selected = []

        if intent.get("product_id"):

            product = engine.get_product(
                intent["product_id"]
            )

            if (
                product
                and engine.is_available(product)
            ):

                selected.append(product)

        # ----------------------------------------------------
        # Health recommendation
        # ----------------------------------------------------

        if KnowledgeLayer.is_medical(
            message
        ):

            knowledge = KnowledgeLayer.answer(
                message
            )

            lines = [
                knowledge.strip(),
                "",
            ]

            if selected:

                product = selected[0]

                price = engine.effective_price(
                    product
                )

                price_text = (
                    format_price(price)
                    if price > 0
                    else "قیمت ثبت نشده"
                )

                lines.extend(
                    [
                        f"🍯 در {STORE_NAME}، "
                        f"«{product.get('title', 'محصول')}» "
                        "در حال حاضر موجوده.",
                        f"💰 {price_text}",
                    ]
                )

            else:

                # Only recommend real honey products.
                honey_products = [
                    p
                    for p in available
                    if (
                        "عسل"
                        in normalize_text(
                            p.get("title", "")
                        )
                        or
                        "عسل"
                        in normalize_text(
                            p.get(
                                "category_name",
                                "",
                            )
                        )
                    )
                ]

                if honey_products:

                    lines.append(
                        f"🍯 از بین عسل‌های موجود "
                        f"{STORE_NAME}، این گزینه‌ها "
                        "در حال حاضر در فروشگاه ثبت شده‌اند:"
                    )

                    for product in honey_products[:5]:

                        title = (
                            product.get("title")
                            or "عسل"
                        )

                        price = engine.effective_price(
                            product
                        )

                        price_text = (
                            format_price(price)
                            if price > 0
                            else "قیمت ثبت نشده"
                        )

                        lines.append(
                            f"• {title} — {price_text}"
                        )

                    lines.extend(
                        [
                            "",
                            "من از روی اطلاعات فروشگاه "
                            "نمی‌تونم ادعا کنم یکی از این عسل‌ها "
                            "حتماً از دیگری برای درمان گلودرد "
                            "بهتره؛ چنین ادعایی نیاز به شواهد "
                            "معتبر داره.",
                        ]
                    )

            return "\n".join(
                lines
            ).strip()

        # ----------------------------------------------------
        # Normal recommendation
        # ----------------------------------------------------

        ranked = sorted(
            available,
            key=lambda p: (
                1
                if p.get("is_popular")
                else 0,
                1
                if engine.has_real_discount(p)
                else 0,
                p.get("id", 0),
            ),
            reverse=True,
        )

        ranked = ranked[:5]

        lines = [
            f"🐝 اگر بخوام از بین محصولات واقعی "
            f"{STORE_NAME} پیشنهاد بدم:",
            "",
        ]

        for product in ranked:

            title = (
                product.get("title")
                or "محصول"
            )

            price = engine.effective_price(
                product
            )

            price_text = (
                format_price(price)
                if price > 0
                else "قیمت ثبت نشده"
            )

            lines.append(
                f"• 🍯 {title} — {price_text}"
            )

        lines.extend(
            [
                "",
                "اگه بگی برای چه مصرفی می‌خوای، "
                "می‌تونم دقیق‌تر راهنماییت کنم.",
            ]
        )

        return "\n".join(
            lines
        ).strip()

    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    @staticmethod
    def category(
        intent: dict,
        engine: ProductEngine,
    ) -> str:

        query = (
            intent.get(
                "query"
            )
            or ""
        ).strip()

        if not query:

            categories = engine.get_categories()

            if not categories:

                return (
                    f"فعلاً دسته‌بندی‌ای در {STORE_NAME} "
                    "ثبت نشده."
                )

            return (
                f"📂 دسته‌بندی‌های {STORE_NAME}:\n\n"
                +
                "\n".join(
                    f"• {item.get('name', '')}"
                    for item in categories
                    if item.get("name")
                )
            )

        category = engine.find_category(
            query
        )

        if not category:

            return (
                f"📂 دسته «{query}» رو در اطلاعات فعلی "
                f"{STORE_NAME} پیدا نکردم."
            )

        products = engine.products_by_category(
            category.get("name", query)
        )

        if not products:

            return (
                f"📂 در دسته «{category.get('name', query)}» "
                "فعلاً محصولی ثبت نشده."
            )

        lines = [
            f"📂 محصولات دسته "
            f"«{category.get('name', query)}»:",
            "",
        ]

        for product in products:

            title = (
                product.get("title")
                or "محصول"
            )

            price = engine.effective_price(
                product
            )

            price_text = (
                format_price(price)
                if price > 0
                else "قیمت ثبت نشده"
            )

            status = (
                "✅ موجود"
                if engine.is_available(product)
                else "❌ ناموجود"
            )

            lines.append(
                f"• 🍯 {title} — "
                f"{price_text} — {status}"
            )

        return "\n".join(
            lines
        )


# ============================================================
# CONVERSATION MEMORY
# ============================================================

class ConversationMemory:

    def __init__(
        self,
        app=None,
    ):

        self.app = app

        self.ensure_tables()

    @staticmethod
    def now() -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    def ensure_tables(self):

        connection = get_connection(
            self.app
        )

        try:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shahdyar_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    message_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shahdyar_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_shahdyar_messages_chat
                ON shahdyar_messages(chat_id)
                """
            )

            connection.commit()

        finally:

            connection.close()

    def create(
        self,
        user_id: str,
    ) -> dict:

        chat_id = (
            "shd_"
            + uuid.uuid4().hex
        )

        now = self.now()

        connection = get_connection(
            self.app
        )

        try:

            connection.execute(
                """
                INSERT INTO shahdyar_chats (
                    chat_id,
                    user_id,
                    status,
                    message_count,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 'active', 0, ?, ?)
                """,
                (
                    chat_id,
                    str(user_id),
                    now,
                    now,
                ),
            )

            connection.commit()

        finally:

            connection.close()

        return self.get(
            chat_id,
            str(user_id),
        )

    def get(
        self,
        chat_id: str,
        user_id: str,
    ) -> Optional[dict]:

        connection = get_connection(
            self.app
        )

        try:

            row = connection.execute(
                """
                SELECT *
                FROM shahdyar_chats
                WHERE chat_id = ?
                AND user_id = ?
                LIMIT 1
                """,
                (
                    str(chat_id),
                    str(user_id),
                ),
            ).fetchone()

            if not row:
                return None

            chat = dict(row)

        finally:

            connection.close()

        self.expire_if_needed(
            chat
        )

        connection = get_connection(
            self.app
        )

        try:

            row = connection.execute(
                """
                SELECT *
                FROM shahdyar_chats
                WHERE chat_id = ?
                AND user_id = ?
                LIMIT 1
                """,
                (
                    str(chat_id),
                    str(user_id),
                ),
            ).fetchone()

            return (
                dict(row)
                if row
                else None
            )

        finally:

            connection.close()

    def expire_if_needed(
        self,
        chat: dict,
    ):

        if chat.get("status") != "active":
            return

        updated_at = chat.get(
            "updated_at"
        )

        if not updated_at:
            return

        try:

            updated = datetime.fromisoformat(
                str(updated_at)
            )

            if (
                datetime.now()
                - updated
                >
                timedelta(
                    minutes=SESSION_TTL_MINUTES
                )
            ):

                self.close(
                    chat["chat_id"]
                )

        except Exception:
            pass

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
    ) -> bool:

        content = (
            content or ""
        ).strip()

        if not content:
            return False

        connection = get_connection(
            self.app
        )

        try:

            row = connection.execute(
                """
                SELECT status, message_count
                FROM shahdyar_chats
                WHERE chat_id = ?
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()

            if not row:
                return False

            if row["status"] != "active":
                return False

            count = int(
                row["message_count"] or 0
            )

            # فقط پیام‌های کاربر سقف ۵۰تایی را مصرف می‌کنند.
            if role == "user":

                if count >= MAX_MESSAGES:
                    return False

            now = self.now()

            connection.execute(
                """
                INSERT INTO shahdyar_messages (
                    chat_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    chat_id,
                    role,
                    content,
                    now,
                ),
            )

            if role == "user":

                connection.execute(
                    """
                    UPDATE shahdyar_chats
                    SET
                        message_count =
                            message_count + 1,
                        updated_at = ?
                    WHERE chat_id = ?
                    """,
                    (
                        now,
                        chat_id,
                    ),
                )

            else:

                connection.execute(
                    """
                    UPDATE shahdyar_chats
                    SET updated_at = ?
                    WHERE chat_id = ?
                    """,
                    (
                        now,
                        chat_id,
                    ),
                )

            connection.commit()

            return True

        finally:

            connection.close()

    def messages(
        self,
        chat_id: str,
    ) -> list[dict]:

        connection = get_connection(
            self.app
        )

        try:

            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    role,
                    content,
                    created_at
                FROM shahdyar_messages
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            connection.close()

    def context(
        self,
        chat_id: str,
    ) -> list[dict]:

        return self.messages(
            chat_id
        )[
            -MAX_CONTEXT_MESSAGES:
        ]

    def can_send(
        self,
        chat: dict,
    ) -> bool:

        if not chat:
            return False

        if chat.get("status") != "active":
            return False

        return (
            int(
                chat.get(
                    "message_count",
                    0,
                )
                or 0
            )
            <
            MAX_MESSAGES
        )

    def close(
        self,
        chat_id: str,
    ):

        now = self.now()

        connection = get_connection(
            self.app
        )

        try:

            connection.execute(
                """
                UPDATE shahdyar_chats
                SET
                    status = 'closed',
                    closed_at = ?,
                    updated_at = ?
                WHERE chat_id = ?
                """,
                (
                    now,
                    now,
                    chat_id,
                ),
            )

            connection.commit()

        finally:

            connection.close()

    def delete(
        self,
        chat_id: str,
    ):

        connection = get_connection(
            self.app
        )

        try:

            connection.execute(
                """
                DELETE FROM shahdyar_messages
                WHERE chat_id = ?
                """,
                (chat_id,),
            )

            connection.execute(
                """
                DELETE FROM shahdyar_chats
                WHERE chat_id = ?
                """,
                (chat_id,),
            )

            connection.commit()

        finally:

            connection.close()


# ============================================================
# PROVIDER ORCHESTRATOR
# ============================================================

class ProviderOrchestrator:

    def __init__(
        self,
        app=None,
    ):

        self.app = app

    # --------------------------------------------------------
    # Config
    # --------------------------------------------------------

    def config(
        self,
        provider: str,
    ) -> dict:

        if provider == "openrouter":

            return {
                "api_key": env(
                    "OPENROUTER_API_KEY"
                ),
                "url": (
                    env(
                        "OPENROUTER_API_URL"
                    )
                    or
                    "https://openrouter.ai/api/v1/chat/completions"
                ),
                "model": (
                    env(
                        "OPENROUTER_MODEL"
                    )
                    or
                    "openai/gpt-oss-120b:free"
                ),
            }

        if provider == "cloudflare":

            return {
                "api_token": env(
                    "CLOUDFLARE_API_TOKEN",
                    "CLOUDFLARE_API_KEY",
                ),
                "account_id": env(
                    "CLOUDFLARE_ACCOUNT_ID"
                ),
                "url": env(
                    "CLOUDFLARE_API_URL"
                ),
                "model": (
                    env(
                        "CLOUDFLARE_MODEL"
                    )
                    or
                    "@cf/meta/llama-3.1-8b-instruct"
                ),
            }

        if provider == "aionlabs":

            return {
                "api_key": env(
                    "AIONLABS_API_KEY"
                ),
                "url": env(
                    "AIONLABS_API_URL"
                ),
                "model": env(
                    "AIONLABS_MODEL"
                ),
            }

        if provider == "cerebras":

            return {
                "api_key": env(
                    "CEREBRAS_API_KEY"
                ),
                "url": (
                    env(
                        "CEREBRAS_API_URL"
                    )
                    or
                    "https://api.cerebras.ai/v1/chat/completions"
                ),
                "model": (
                    env(
                        "CEREBRAS_MODEL"
                    )
                    or
                    "llama-3.3-70b"
                ),
            }

        return {}

    # --------------------------------------------------------
    # Enabled
    # --------------------------------------------------------

    def enabled_providers(self) -> list[str]:

        enabled = []

        for provider in PROVIDER_ORDER:

            config = self.config(
                provider
            )

            if provider == "openrouter":

                if config.get("api_key"):
                    enabled.append(provider)

            elif provider == "cloudflare":

                if (
                    config.get("api_token")
                    and
                    config.get("account_id")
                ):
                    enabled.append(provider)

            elif provider == "aionlabs":

                if all(
                    (
                        config.get("api_key"),
                        config.get("url"),
                        config.get("model"),
                    )
                ):
                    enabled.append(provider)

            elif provider == "cerebras":

                if config.get("api_key"):
                    enabled.append(provider)

        return enabled

    # --------------------------------------------------------
    # System prompt
    # --------------------------------------------------------

    @staticmethod
    def system_prompt(
        site_snapshot: str,
        knowledge: str,
    ) -> str:

        return f"""
تو «شهدیار» هستی؛ دستیار هوشمند و صمیمی سایت «{STORE_NAME}».

هویت:
- نام: شهدیار
- سایت: {STORE_NAME}
- سازنده و زنبوردار باتجربه: {STORE_CREATOR}
- منطقه فعالیت: {STORE_LOCATION}

درباره سازنده:
{STORE_CREATOR} یک زنبوردار با سابقه و با تجربه در پرورش
زنبور عسل و فرآورده‌های زنبور عسل در استان لرستان،
شهرستان بروجرد است.

ماموریت تو:
تو فقط ربات فروش محصول نیستی.
تو نماینده هوشمند شهدآور هستی و باید به کاربر کمک کنی
هم اطلاعات عمومی مفید بگیرد و هم سایت شهدآور را بهتر
بشناسد.

========================
قوانین بسیار مهم
========================

1. اطلاعات فروشگاه را هرگز حدس نزن.

2. نام محصول، قیمت، تخفیف، موجودی، دسته‌بندی یا ویژگی
فروشگاهی را فقط از اطلاعات واقعی سایت استفاده کن.

3. اگر قیمت در اطلاعات سایت وجود ندارد، قیمت نساز.
بگو:
«قیمت دقیق در اطلاعات فعلی ثبت نشده و می‌تونی با
پشتیبانی آنلاین شهدآور در ارتباط باشی.»

4. اگر محصولی در سایت وجود ندارد، نگو موجود است.

5. هیچ محصول یا برند خارج از شهدآور را تبلیغ نکن.

6. اگر درباره یک موضوع عمومی سؤال شد، حتماً می‌توانی
از دانش عمومی خودت استفاده کنی.

7. اگر سؤال عمومی به محصولات شهدآور مربوط می‌شود،
اول توضیح عمومی بده و سپس در صورت وجود محصول واقعی،
آن را به کاربر معرفی کن.

8. درباره مسائل پزشکی تشخیص یا تضمین درمان نده.

9. عبارت‌هایی مثل «درمان قطعی»، «صددرصد درمان می‌کند»
یا ادعاهای پزشکی اثبات‌نشده درباره محصولات شهدآور
نساز.

10. اگر کاربر مثلاً بپرسد:
«چه عسلی برای درمان گلودرد خوبه؟»

باید:
الف) اطلاعات عمومی و محتاطانه درباره گلودرد و عسل بدهی.
ب) سپس محصولات واقعی عسل موجود در شهدآور را معرفی کنی.
ج) قیمت فقط اگر در snapshot واقعی وجود دارد.
د) ادعا نکنی یک محصول خاص درمان قطعی است.

11. از اعتبار شهدآور و تجربه رضا رحیمی طبیعی و بدون
اغراق استفاده کن.

12. لحن:
- فارسی
- دوستانه
- صمیمی
- طبیعی
- گرم
- حرفه‌ای
- نه خشک
- نه ماشینی
- نه بیش از حد تبلیغاتی

13. کاربر نباید احساس کند با یک ربات پاسخ‌گوی خشک حرف
می‌زند.

14. وقتی موضوع به شهدآور مرتبط است، از سایت حمایت کن؛
اما تبلیغ مصنوعی و بی‌ربط انجام نده.

15. اگر اطلاعات سایت برای پاسخ کافی نیست، صادقانه بگو
اطلاعات کافی در دسترس نیست و کاربر را به پشتیبانی
آنلاین شهدآور راهنمایی کن.

16. هرگز قیمت یا اطلاعات سایت را از دانش عمومی خودت
جایگزین نکن.

17. دانش عمومی زیر فقط برای پاسخ علمی/عمومی است و
نباید به عنوان اطلاعات فروشگاه معرفی شود.

========================
دانش عمومی مرتبط
========================

{knowledge}

========================
اطلاعات واقعی سایت شهدآور
========================

{site_snapshot}

========================
دستور نهایی
========================

پاسخ را طبیعی و کاربردی بده.
اگر سؤال عمومی است، فقط به فروشگاه گیر نده.
اگر سؤال فروشگاهی است، از اطلاعات واقعی سایت استفاده کن.
اگر سؤال عمومی و فروشگاهی هر دو هستند، این دو را با هم
ترکیب کن.

هیچ وقت اطلاعات ساختگی تولید نکن.
""".strip()

    # --------------------------------------------------------
    # OpenAI-compatible
    # --------------------------------------------------------

    def _openai_request(
        self,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict],
    ) -> Optional[str]:

        if not all(
            (
                url,
                api_key,
                model,
            )
        ):
            return None

        headers = {
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.45,
            "max_tokens": 1200,
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=HTTP_TIMEOUT,
        )

        if not response.ok:

            logger.warning(
                "Provider HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )

            return None

        data = response.json()

        choices = data.get(
            "choices"
        )

        if choices:

            message = choices[0].get(
                "message",
                {}
            )

            content = message.get(
                "content"
            )

            if isinstance(
                content,
                list,
            ):

                parts = []

                for part in content:

                    if isinstance(part, dict):

                        text = part.get(
                            "text",
                            "",
                        )

                        if text:
                            parts.append(
                                str(text)
                            )

                content = "".join(parts)

            if content:

                return str(
                    content
                ).strip()

        return None

    # --------------------------------------------------------
    # OpenRouter
    # --------------------------------------------------------

    def call_openrouter(
        self,
        messages: list[dict],
    ) -> Optional[str]:

        config = self.config(
            "openrouter"
        )

        if not config.get("api_key"):
            return None

        return self._openai_request(
            config["url"],
            config["api_key"],
            config["model"],
            messages,
        )

    # --------------------------------------------------------
    # Cloudflare
    # --------------------------------------------------------

    def call_cloudflare(
        self,
        messages: list[dict],
    ) -> Optional[str]:

        config = self.config(
            "cloudflare"
        )

        token = config.get(
            "api_token"
        )

        account_id = config.get(
            "account_id"
        )

        model = config.get(
            "model"
        )

        if not token or not account_id:
            return None

        url = config.get("url")

        if not url:

            url = (
                "https://api.cloudflare.com/client/v4/"
                f"accounts/{account_id}/ai/run/{model}"
            )

        headers = {
            "Authorization":
                f"Bearer {token}",
            "Content-Type":
                "application/json",
        }

        response = requests.post(
            url,
            headers=headers,
            json={
                "messages": messages
            },
            timeout=HTTP_TIMEOUT,
        )

        if not response.ok:

            logger.warning(
                "Cloudflare HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )

            return None

        data = response.json()

        result = data.get(
            "result"
        )

        if isinstance(
            result,
            dict,
        ):

            return str(
                result.get(
                    "response"
                )
                or
                result.get(
                    "text"
                )
                or
                result.get(
                    "content"
                )
                or ""
            ).strip() or None

        return None

    # --------------------------------------------------------
    # Aion Labs
    # --------------------------------------------------------

    def call_aionlabs(
        self,
        messages: list[dict],
    ) -> Optional[str]:

        config = self.config(
            "aionlabs"
        )

        if not all(
            (
                config.get("api_key"),
                config.get("url"),
                config.get("model"),
            )
        ):
            return None

        return self._openai_request(
            config["url"],
            config["api_key"],
            config["model"],
            messages,
        )

    # --------------------------------------------------------
    # Cerebras
    # --------------------------------------------------------

    def call_cerebras(
        self,
        messages: list[dict],
    ) -> Optional[str]:

        config = self.config(
            "cerebras"
        )

        if not config.get("api_key"):
            return None

        return self._openai_request(
            config["url"],
            config["api_key"],
            config["model"],
            messages,
        )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    def generate(
        self,
        messages: list[dict],
    ) -> Optional[str]:

        callers = {
            "openrouter":
                self.call_openrouter,

            "cloudflare":
                self.call_cloudflare,

            "aionlabs":
                self.call_aionlabs,

            "cerebras":
                self.call_cerebras,
        }

        enabled = (
            self.enabled_providers()
        )

        logger.info(
            "Provider chain: %s",
            enabled,
        )

        for provider in PROVIDER_ORDER:

            if provider not in enabled:
                continue

            try:

                logger.info(
                    "Trying %s",
                    provider,
                )

                answer = callers[
                    provider
                ](
                    messages
                )

                if answer:

                    logger.info(
                        "Provider success: %s",
                        provider,
                    )

                    return answer

            except requests.RequestException as error:

                logger.warning(
                    "%s request error: %s",
                    provider,
                    error,
                )

            except Exception as error:

                logger.exception(
                    "%s provider error: %s",
                    provider,
                    error,
                )

        return None


# ============================================================
# VALIDATOR
# ============================================================

class Validator:

    @staticmethod
    def clean(
        text: Any,
    ) -> str:

        if text is None:
            return ""

        value = str(
            text
        ).strip()

        value = re.sub(
            r"\n{4,}",
            "\n\n",
            value,
        )

        if len(value) > 6000:

            value = value[:6000].rstrip()

        return value

    @classmethod
    def validate(
        cls,
        text: Any,
    ) -> Optional[str]:

        value = cls.clean(
            text
        )

        if not value:
            return None

        lower = value.lower()

        forbidden = (
            "api_key=",
            "apikey=",
            "authorization:",
            "bearer ",
            "secret_key=",
            "access_token=",
        )

        if any(
            item in lower
            for item in forbidden
        ):
            return None

        return value


# ============================================================
# GENERAL AI RESPONSE
# ============================================================

def _general_ai_response(
    app,
    chat: dict,
    message: str,
) -> str:

    memory = ConversationMemory(
        app
    )

    engine = ProductEngine(
        app
    )

    site_snapshot = (
        SiteKnowledge.build_snapshot(
            app
        )
    )

    knowledge = (
        KnowledgeLayer.answer(
            message
        )
    )

    provider = ProviderOrchestrator(
        app
    )

    system = provider.system_prompt(
        site_snapshot=site_snapshot,
        knowledge=knowledge,
    )

    messages = [
        {
            "role": "system",
            "content": system,
        }
    ]

    for item in memory.context(
        chat["chat_id"]
    ):

        role = item.get(
            "role"
        )

        content = item.get(
            "content"
        )

        if (
            role in {
                "user",
                "assistant",
            }
            and content
        ):

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    messages.append(
        {
            "role": "user",
            "content": message,
        }
    )

    answer = provider.generate(
        messages
    )

    validated = Validator.validate(
        answer
    )

    if validated:
        return validated

    # حتی اگر APIها قطع باشند، شهدیار باید دانش پایه داشته باشد.
    if KnowledgeLayer.is_medical(
        message
    ):

        return (
            KnowledgeLayer.answer(
                message
            )
            +
            "\n\n"
            "🍯 اگر دوست داشته باشی، می‌تونم محصولات "
            "موجود شهدآور رو هم بر اساس اطلاعات واقعی "
            "فروشگاه برات بررسی کنم."
        )

    # اطلاعات عمومی پایه
    return (
        KnowledgeLayer.answer(
            message
        )
        +
        "\n\n"
        "🐝 اگر سؤال دقیق‌تری داری بپرس؛ "
        "شهدیار سعی می‌کنه بر اساس اطلاعات واقعی "
        "شهدآور و دانش عمومی مرتبط راهنماییت کنه."
    )


# ============================================================
# PUBLIC API
# ============================================================

def create_chat_session(
    user_id,
) -> dict:

    memory = ConversationMemory()

    return memory.create(
        str(user_id)
    )


def get_chat_session(
    chat_id,
    user_id,
) -> Optional[dict]:

    memory = ConversationMemory()

    return memory.get(
        str(chat_id),
        str(user_id),
    )


def delete_chat_session(
    chat_id,
    user_id=None,
):

    memory = ConversationMemory()

    if user_id is not None:

        chat = memory.get(
            str(chat_id),
            str(user_id),
        )

        if not chat:
            return False

    memory.delete(
        str(chat_id)
    )

    return True


def can_send_message(
    chat: dict,
) -> bool:

    memory = ConversationMemory()

    return memory.can_send(
        chat
    )


def get_messages(
    chat: dict,
) -> list[dict]:

    if not chat:
        return []

    memory = ConversationMemory()

    return memory.messages(
        chat["chat_id"]
    )


def get_chat_status(
    chat: dict,
) -> dict:

    if not chat:

        return {
            "chat_id": None,
            "status": "closed",
            "message_count": 0,
            "max_messages": MAX_MESSAGES,
            "remaining_messages": 0,
        }

    count = int(
        chat.get(
            "message_count",
            0,
        )
        or 0
    )

    return {
        "chat_id":
            chat.get("chat_id"),

        "status":
            chat.get(
                "status",
                "active",
            ),

        "message_count":
            count,

        "max_messages":
            MAX_MESSAGES,

        "remaining_messages":
            max(
                0,
                MAX_MESSAGES - count,
            ),

        "created_at":
            chat.get("created_at"),

        "updated_at":
            chat.get("updated_at"),

        "closed_at":
            chat.get("closed_at"),
    }


# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_ai_response(
    app,
    chat: dict,
    message: str,
) -> str:

    message = (
        message or ""
    ).strip()

    if not message:

        return (
            "🐝 بگو ببینم چه چیزی می‌خوای بدونی؟"
        )

    if len(message) > 8000:

        return (
            "پیامت یه مقدار طولانیه 😄 "
            "لطفاً کوتاه‌ترش کن تا بهتر بتونم بررسیش کنم."
        )

    if not chat:

        return (
            "گفت‌وگوی فعلی معتبر نیست. "
            "لطفاً یک گفت‌وگوی جدید شروع کن."
        )

    memory = ConversationMemory(
        app
    )

    # --------------------------------------------------------
    # Refresh chat
    # --------------------------------------------------------

    refreshed = None

    try:

        refreshed = memory.get(
            chat["chat_id"],
            str(
                chat.get(
                    "user_id",
                    "",
                )
            ),
        )

    except Exception:
        pass

    if not refreshed:
        refreshed = chat

    # --------------------------------------------------------
    # Limit
    # --------------------------------------------------------

    if not memory.can_send(
        refreshed
    ):

        if (
            refreshed.get(
                "status"
            )
            !=
            "active"
        ):

            return (
                "⏱️ این گفت‌وگو منقضی شده. "
                "لطفاً یک گفت‌وگوی جدید شروع کن."
            )

        return (
            "📌 سقف ۵۰ پیام این گفت‌وگو پر شده. "
            "لطفاً یک گفت‌وگوی جدید شروع کن."
        )

    # --------------------------------------------------------
    # Engines
    # --------------------------------------------------------

    engine = ProductEngine(
        app
    )

    # --------------------------------------------------------
    # Intent
    # --------------------------------------------------------

    intent = IntentEngine.classify(
        message,
        engine,
    )

    logger.info(
        "Intent=%s | Query=%s | Confidence=%s",
        intent.get("intent"),
        intent.get("query"),
        intent.get("confidence"),
    )

    # --------------------------------------------------------
    # Save user message
    # --------------------------------------------------------

    saved = memory.add_message(
        refreshed["chat_id"],
        "user",
        message,
    )

    if not saved:

        return (
            "متأسفانه نتونستم پیام رو در گفت‌وگو ثبت کنم. "
            "لطفاً دوباره امتحان کن."
        )

    # --------------------------------------------------------
    # Deterministic store / mixed responses
    # --------------------------------------------------------

    answer = None

    intent_name = intent.get(
        "intent"
    )

    if intent_name == "greeting":

        answer = ResponseComposer.greeting()

    elif intent_name == "product_catalog":

        answer = engine.build_catalog_response()

    elif intent_name == "product_detail":

        answer = (
            ResponseComposer.product_detail(
                message,
                intent,
                engine,
            )
        )

    elif intent_name == "product_price":

        answer = (
            ResponseComposer.product_price(
                message,
                intent,
                engine,
            )
        )

    elif intent_name == "product_availability":

        answer = (
            ResponseComposer.product_availability(
                message,
                intent,
                engine,
            )
        )

    elif intent_name == "category_browse":

        answer = (
            ResponseComposer.category(
                intent,
                engine,
            )
        )

    elif intent_name == "recommendation":

        answer = (
            ResponseComposer.recommendation(
                message,
                intent,
                engine,
            )
        )

    elif intent_name == "knowledge_with_products":

        answer = (
            ResponseComposer.knowledge_with_products(
                message,
                engine,
            )
        )

    elif intent_name == "order_support":

        answer = (
            "🛒 حتماً رفیق. برای خرید، محصول موردنظرت "
            "رو از سایت شهدآور انتخاب کن و وارد صفحه "
            "همون محصول شو.\n\n"
            "اگر درباره قیمت، موجودی یا مشخصات یک محصول "
            "سؤال داری، اسمش رو بفرست تا بر اساس اطلاعات "
            "واقعی سایت راهنماییت کنم."
        )

    elif intent_name == "support":

        answer = (
            "🐝 حتماً رفیق. مشکلت یا چیزی که می‌خوای "
            "درباره شهدآور بدونی رو بگو.\n\n"
            "اگر اطلاعاتش در داده‌های سایت نباشه، "
            "نمی‌خوام حدس بزنم؛ در اون حالت می‌تونی "
            "با پشتیبانی آنلاین شهدآور در ارتباط باشی."
        )

    # --------------------------------------------------------
    # General AI
    # --------------------------------------------------------

    if not answer:

        answer = _general_ai_response(
            app,
            refreshed,
            message,
        )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    answer = (
        Validator.validate(
            answer
        )
        or
        "🐝 یه لحظه نتونستم پاسخ مناسبی آماده کنم. "
        "دوباره بپرس."
    )

    # --------------------------------------------------------
    # Save assistant
    # --------------------------------------------------------

    memory.add_message(
        refreshed["chat_id"],
        "assistant",
        answer,
    )

    return answer


# ============================================================
# PROVIDER STATUS
# ============================================================

def get_provider_status() -> dict:

    orchestrator = (
        ProviderOrchestrator()
    )

    providers = {}

    for provider in PROVIDER_ORDER:

        config = orchestrator.config(
            provider
        )

        if provider == "openrouter":

            configured = bool(
                config.get("api_key")
            )

        elif provider == "cloudflare":

            configured = bool(
                config.get("api_token")
                and
                config.get("account_id")
            )

        elif provider == "aionlabs":

            configured = bool(
                config.get("api_key")
                and
                config.get("url")
                and
                config.get("model")
            )

        elif provider == "cerebras":

            configured = bool(
                config.get("api_key")
            )

        else:

            configured = False

        providers[provider] = {
            "configured": configured,
            "enabled": configured,
        }

    return {
        "providers": providers,
        "order": list(
            PROVIDER_ORDER
        ),
        "active_chain": (
            orchestrator.enabled_providers()
        ),
    }


# ============================================================
# SITE KNOWLEDGE STATUS
# ============================================================

def get_site_knowledge_status(
    app=None,
) -> dict:

    database_path = (
        _resolve_database_path(
            app
        )
    )

    try:

        engine = ProductEngine(
            app
        )

        products = (
            engine.get_all_products()
        )

        available = [
            p
            for p in products
            if engine.is_available(p)
        ]

        categories = (
            engine.get_categories()
        )

        site_snapshot = (
            SiteKnowledge.build_snapshot(
                app
            )
        )

        return {
            "database":
                str(database_path),

            "database_exists":
                database_path.exists(),

            "products":
                len(products),

            "available_products":
                len(available),

            "categories":
                len(categories),

            "site_knowledge_chars":
                len(site_snapshot),

            "site_knowledge_loaded":
                bool(site_snapshot),
        }

    except Exception as error:

        logger.exception(
            "Site knowledge status error: %s",
            error,
        )

        return {
            "database":
                str(database_path),

            "database_exists":
                database_path.exists(),

            "products": 0,
            "available_products": 0,
            "categories": 0,

            "site_knowledge_chars": 0,

            "site_knowledge_loaded":
                False,

            "error":
                str(error),
        }


# ============================================================
# SELF TEST
# ============================================================

def self_test(
    app=None,
) -> dict:

    result = {
        "ok": True,
        "database": {},
        "site": {},
        "products": [],
        "providers": {},
    }

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    try:

        path = _resolve_database_path(
            app
        )

        result["database"] = {
            "path":
                str(path),

            "exists":
                path.exists(),
        }

    except Exception as error:

        result["database"] = {
            "error":
                str(error),
        }

        result["ok"] = False

    # --------------------------------------------------------
    # Site
    # --------------------------------------------------------

    try:

        result["site"] = (
            get_site_knowledge_status(
                app
            )
        )

    except Exception as error:

        result["site"] = {
            "error":
                str(error),
        }

        result["ok"] = False

    # --------------------------------------------------------
    # Products
    # --------------------------------------------------------

    try:

        engine = ProductEngine(
            app
        )

        for product in engine.get_all_products():

            result["products"].append(
                {
                    "id":
                        product.get("id"),

                    "title":
                        product.get("title"),

                    "price":
                        product.get("price"),

                    "final_price":
                        product.get(
                            "final_price"
                        ),

                    "effective_price":
                        engine.effective_price(
                            product
                        ),

                    "discount":
                        engine.has_real_discount(
                            product
                        ),

                    "available":
                        engine.is_available(
                            product
                        ),

                    "category":
                        product.get(
                            "category_name"
                        ),
                }
            )

    except Exception as error:

        result["products_error"] = (
            str(error)
        )

        result["ok"] = False

    # --------------------------------------------------------
    # Providers
    # --------------------------------------------------------

    try:

        result["providers"] = (
            get_provider_status()
        )

    except Exception as error:

        result["providers"] = {
            "error":
                str(error),
        }

        result["ok"] = False

    return result


# ============================================================
# MODULE LOAD
# ============================================================

try:

    logger.info(
        "Shahdyar project root: %s",
        Path(
            __file__
        ).resolve().parent.parent,
    )

    logger.info(
        "Shahdyar database: %s",
        _resolve_database_path(),
    )

    logger.info(
        "Database exists: %s",
        _resolve_database_path().exists(),
    )

    logger.info(
        "Provider chain: %s",
        ProviderOrchestrator()
        .enabled_providers(),
    )

    logger.info(
        "Shahdyar service loaded successfully."
    )

except Exception as error:

    logger.exception(
        "Shahdyar initialization error: %s",
        error,
    )