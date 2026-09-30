from __future__ import annotations

import sqlite3
import json
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone


def _persian_digits(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _support_time_display(value):
    if not value:
        return ""
    try:
        raw = str(value).replace("Z", "").strip()
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tehran = dt.astimezone(timezone(timedelta(hours=3, minutes=30)))
        now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
        if tehran.date() == now.date():
            return "امروز، " + _persian_digits(tehran.strftime("%H:%M"))
        if tehran.date() == (now - timedelta(days=1)).date():
            return "دیروز، " + _persian_digits(tehran.strftime("%H:%M"))
        return _persian_digits(tehran.strftime("%Y/%m/%d - %H:%M"))
    except Exception:
        return str(value)


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "honeyshop.db"


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def _table_columns(cursor, table_name):
    return {row["name"] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_column(cursor, table_name, column_name, definition):
    if column_name in _table_columns(cursor, table_name):
        return False
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
    return True


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    connection = get_connection()
    cursor = connection.cursor()

    # ========================================================
    # SITE SETTINGS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_settings (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            site_name TEXT DEFAULT 'عسل شهدآور',

            site_tagline TEXT DEFAULT 'طعم واقعی طبیعت',

            welcome_text TEXT DEFAULT
                'سلام دوست عزیز؛ به بهشت عسل شهدآور خوش اومدی!',

            about_text TEXT DEFAULT '',

            support_text TEXT DEFAULT '',

            contact_text TEXT DEFAULT '',

            contact_title TEXT DEFAULT 'تماس با شهدآور',

            contact_button_text TEXT DEFAULT 'تماس با ما',

            background_color TEXT DEFAULT '#fffdf8',

            banner TEXT DEFAULT ''
        )
    """)

    # ========================================================
    # SITE SETTINGS MIGRATION
    # ========================================================

    site_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(site_settings)"
        ).fetchall()
    }

    site_migrations = {

        "contact_title": """
            ALTER TABLE site_settings
            ADD COLUMN contact_title TEXT
            DEFAULT 'تماس با شهدآور'
        """,

        "contact_button_text": """
            ALTER TABLE site_settings
            ADD COLUMN contact_button_text TEXT
            DEFAULT 'تماس با ما'
        """,
    }

    for column_name, sql in site_migrations.items():

        if column_name not in site_columns:

            try:

                cursor.execute(sql)

            except sqlite3.OperationalError:

                pass

    # ========================================================
    # CATEGORIES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL UNIQUE,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # PRODUCTS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            price TEXT NOT NULL,

            description TEXT,

            category_id INTEGER,

            status TEXT DEFAULT 'normal',

            discount_percent TEXT,

            final_price TEXT,

            discount_days INTEGER,

            discount_expires_at TEXT,

            image_1 TEXT,

            image_2 TEXT,

            image_3 TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(category_id)
                REFERENCES categories(id)
        )
    """)

    # ========================================================
    # PRODUCT MIGRATION
    # ========================================================

    product_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    }

    product_migrations = {

        "discount_expires_at": """
            ALTER TABLE products
            ADD COLUMN discount_expires_at TEXT
        """,

        "updated_at": """
            ALTER TABLE products
            ADD COLUMN updated_at TEXT
            DEFAULT CURRENT_TIMESTAMP
        """,

        "is_discount": """
            ALTER TABLE products
            ADD COLUMN is_discount INTEGER
            NOT NULL DEFAULT 0
        """,

        "is_popular": """
            ALTER TABLE products
            ADD COLUMN is_popular INTEGER
            NOT NULL DEFAULT 0
        """,

        "is_available": """
            ALTER TABLE products
            ADD COLUMN is_available INTEGER
            NOT NULL DEFAULT 1
        """,

        "tags": """
            ALTER TABLE products
            ADD COLUMN tags TEXT DEFAULT ''
        """,

        "weight": """
            ALTER TABLE products
            ADD COLUMN weight TEXT DEFAULT ''
        """,

        "stock": """
            ALTER TABLE products
            ADD COLUMN stock INTEGER NOT NULL DEFAULT 0
        """,
    }

    for column_name, sql in product_migrations.items():

        if column_name not in product_columns:

            try:

                cursor.execute(sql)

            except sqlite3.OperationalError:

                pass

    # ========================================================
    # MIGRATE OLD PRODUCT STATUS
    # ========================================================

    try:

        cursor.execute("""
            UPDATE products
            SET is_discount = 1
            WHERE status = 'discount'
        """)

        cursor.execute("""
            UPDATE products
            SET is_popular = 1
            WHERE status = 'popular'
        """)

        cursor.execute("""
            UPDATE products
            SET is_available = 0
            WHERE status = 'unavailable'
        """)

    except sqlite3.OperationalError:

        pass

    # ========================================================
    # COVERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS covers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            filename TEXT NOT NULL,

            duration INTEGER DEFAULT 5,

            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Older databases may not have cover ordering.
    try:
        _ensure_column(cursor, "covers", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Normalize existing order without changing which covers exist.
    try:
        for idx, row in enumerate(cursor.execute("SELECT id FROM covers ORDER BY sort_order ASC, id ASC").fetchall()):
            cursor.execute("UPDATE covers SET sort_order = ? WHERE id = ?", (idx, row["id"]))
    except sqlite3.OperationalError:
        pass

    # If the cover table is empty, register the six built-in hero images
    # as real editable covers. This keeps the homepage and owner panel
    # backed by the same data source.
    cover_count = cursor.execute("SELECT COUNT(*) FROM covers").fetchone()[0]
    if cover_count == 0:
        for number in range(1, 7):
            cursor.execute(
                "INSERT INTO covers (filename, duration) VALUES (?, ?)",
                (f"hero-{number}.jpg", 5),
            )

    # ========================================================
    # LOGO
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logo (

            id INTEGER PRIMARY KEY,

            filename TEXT
        )
    """)

    # ========================================================
    # BANNERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banners (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            filename TEXT NOT NULL,

            title TEXT DEFAULT '',

            link TEXT DEFAULT '',

            is_active INTEGER NOT NULL DEFAULT 1,

            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        _ensure_column(cursor, "banners", "is_active", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(cursor, "banners", "sort_order", "INTEGER NOT NULL DEFAULT 0")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_banners_order ON banners(is_active, sort_order, id)")
    except sqlite3.OperationalError:
        pass

    # ========================================================
    # CONTACT METHODS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_methods (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            value TEXT DEFAULT '',

            link TEXT DEFAULT '',

            icon TEXT DEFAULT '',

            platform TEXT DEFAULT '',

            icon_emoji TEXT DEFAULT '📞',

            icon_type TEXT DEFAULT 'emoji',

            description TEXT DEFAULT '',

            button_text TEXT DEFAULT 'ارتباط',

            is_active INTEGER NOT NULL DEFAULT 1,

            sort_order INTEGER NOT NULL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # CONTACT MIGRATION
    # ========================================================

    contact_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(contact_methods)"
        ).fetchall()
    }

    contact_migrations = {

        "value": """
            ALTER TABLE contact_methods
            ADD COLUMN value TEXT DEFAULT ''
        """,

        "link": """
            ALTER TABLE contact_methods
            ADD COLUMN link TEXT DEFAULT ''
        """,

        "icon": """
            ALTER TABLE contact_methods
            ADD COLUMN icon TEXT DEFAULT ''
        """,

        "platform": """
            ALTER TABLE contact_methods
            ADD COLUMN platform TEXT DEFAULT ''
        """,

        "icon_emoji": """
            ALTER TABLE contact_methods
            ADD COLUMN icon_emoji TEXT DEFAULT '📞'
        """,

        "icon_type": """
            ALTER TABLE contact_methods
            ADD COLUMN icon_type TEXT DEFAULT 'emoji'
        """,

        "description": """
            ALTER TABLE contact_methods
            ADD COLUMN description TEXT DEFAULT ''
        """,

        "button_text": """
            ALTER TABLE contact_methods
            ADD COLUMN button_text TEXT DEFAULT 'ارتباط'
        """,

        "is_active": """
            ALTER TABLE contact_methods
            ADD COLUMN is_active INTEGER
            NOT NULL DEFAULT 1
        """,

        "sort_order": """
            ALTER TABLE contact_methods
            ADD COLUMN sort_order INTEGER
            NOT NULL DEFAULT 0
        """,

        "created_at": """
            ALTER TABLE contact_methods
            ADD COLUMN created_at TEXT
            DEFAULT CURRENT_TIMESTAMP
        """,

        "updated_at": """
            ALTER TABLE contact_methods
            ADD COLUMN updated_at TEXT
            DEFAULT CURRENT_TIMESTAMP
        """,
    }

    for column_name, sql in contact_migrations.items():

        if column_name not in contact_columns:

            try:

                cursor.execute(sql)

            except sqlite3.OperationalError:

                pass

    # Existing uploaded icons are images even on databases upgraded
    # from the pre-icon_type schema. Mark them accordingly without
    # touching user-created emoji-only records.
    try:
        cursor.execute("""
            UPDATE contact_methods
            SET icon_type = 'image'
            WHERE COALESCE(TRIM(icon), '') <> ''
              AND (icon_type IS NULL OR icon_type = '' OR icon_type = 'emoji')
        """)
    except sqlite3.OperationalError:
        pass

    # ========================================================
    # CONTACT INDEX
    # ========================================================

    try:

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_contact_methods_order
            ON contact_methods(sort_order, id)
        """)

    except sqlite3.OperationalError:

        pass

    # ========================================================
    # REMOVE OLD AUTOMATIC DEFAULT CONTACT
    # ========================================================
    #
    # نسخه‌های قبلی برنامه یک راه ارتباطی پیش‌فرض ایجاد
    # می‌کردند:
    #
    #   عنوان: تماس با مدیریت
    #   شماره: 09169740802
    #
    # سیستم جدید نباید هیچ راه ارتباطی را به‌صورت خودکار
    # ایجاد کند.
    #
    # بنابراین فقط رکوردی که دقیقاً متعلق به همین
    # مقدار پیش‌فرض قدیمی است حذف می‌شود.
    #
    # راه‌های ارتباطی دیگری که کاربر خودش اضافه کرده
    # دست‌نخورده باقی می‌مانند.
    #
    # ========================================================

    try:

        cursor.execute("""
            DELETE FROM contact_methods
            WHERE title = 'تماس با مدیریت'
              AND value = '09169740802'
              AND link = 'tel:09169740802'
        """)

    except sqlite3.OperationalError:

        pass

    # ========================================================
    # USERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            first_name TEXT NOT NULL DEFAULT '',

            last_name TEXT NOT NULL DEFAULT '',

            phone TEXT NOT NULL UNIQUE,

            email TEXT,

            province TEXT,

            city TEXT,

            gender TEXT NOT NULL DEFAULT 'male',

            password_hash TEXT NOT NULL DEFAULT '',

            avatar TEXT NOT NULL DEFAULT '',

            terms_accepted INTEGER NOT NULL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # USERS MIGRATION
    # ========================================================

    user_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    }

    user_migrations = {

        "first_name": """
            ALTER TABLE users
            ADD COLUMN first_name TEXT
            NOT NULL DEFAULT ''
        """,

        "last_name": """
            ALTER TABLE users
            ADD COLUMN last_name TEXT
            NOT NULL DEFAULT ''
        """,

        "phone": """
            ALTER TABLE users
            ADD COLUMN phone TEXT
            NOT NULL DEFAULT ''
        """,

        "email": """
            ALTER TABLE users
            ADD COLUMN email TEXT
        """,

        "province": """
            ALTER TABLE users
            ADD COLUMN province TEXT
        """,

        "city": """
            ALTER TABLE users
            ADD COLUMN city TEXT
        """,

        "gender": """
            ALTER TABLE users
            ADD COLUMN gender TEXT
            NOT NULL DEFAULT 'male'
        """,

        "password_hash": """
            ALTER TABLE users
            ADD COLUMN password_hash TEXT
            NOT NULL DEFAULT ''
        """,

        "avatar": """
            ALTER TABLE users
            ADD COLUMN avatar TEXT
            NOT NULL DEFAULT ''
        """,

        "terms_accepted": """
            ALTER TABLE users
            ADD COLUMN terms_accepted INTEGER
            NOT NULL DEFAULT 0
        """,

        "created_at": """
            ALTER TABLE users
            ADD COLUMN created_at TEXT
            DEFAULT CURRENT_TIMESTAMP
        """,

        "updated_at": """
            ALTER TABLE users
            ADD COLUMN updated_at TEXT
            DEFAULT CURRENT_TIMESTAMP
        """,
    }

    for column_name, sql in user_migrations.items():

        if column_name not in user_columns:

            try:

                cursor.execute(sql)

            except sqlite3.OperationalError:

                pass

    # ========================================================
    # USER INDEXES
    # ========================================================

    try:

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_users_phone
            ON users(phone)
        """)

    except sqlite3.OperationalError:

        pass

    try:

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_users_email
            ON users(email)
        """)

    except sqlite3.OperationalError:

        pass

    # ========================================================
    # REVIEWS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            comment TEXT NOT NULL,

            rating INTEGER NOT NULL DEFAULT 5 CHECK(rating BETWEEN 1 AND 5),

            status TEXT DEFAULT 'pending',

            owner_reply TEXT DEFAULT '',

            owner_reply_at TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE CASCADE,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    # Preserve review data while adding rating support.
    try:
        _ensure_column(cursor, "reviews", "rating", "INTEGER NOT NULL DEFAULT 5")
        cursor.execute("UPDATE reviews SET rating = 5 WHERE rating IS NULL OR rating < 1 OR rating > 5")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_status ON reviews(product_id, status, id)")
    except sqlite3.OperationalError:
        pass

    # ========================================================
    # EXTENDED SITE / ACCOUNT / SUPPORT SCHEMA
    # ========================================================

    # Editable About page media/content.
    site_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(site_settings)").fetchall()
    }
    extra_site_columns = {
        "about_title": "ALTER TABLE site_settings ADD COLUMN about_title TEXT DEFAULT 'درباره شهدآور'",
        "about_image": "ALTER TABLE site_settings ADD COLUMN about_image TEXT DEFAULT ''",
        "about_link": "ALTER TABLE site_settings ADD COLUMN about_link TEXT DEFAULT ''",
    }
    for column_name, sql in extra_site_columns.items():
        if column_name not in site_columns:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

    # Required unique Latin username for every customer account.
    user_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(users)").fetchall()
    }
    if "username" not in user_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        except sqlite3.OperationalError:
            pass

    # Backfill existing users with deterministic unique usernames.
    existing_users = cursor.execute(
        "SELECT id, first_name, last_name, phone, username FROM users ORDER BY id ASC"
    ).fetchall()
    used_usernames = set()
    for row in existing_users:
        current = (row["username"] or "").strip()
        if current:
            used_usernames.add(current.lower())
    for row in existing_users:
        if (row["username"] or "").strip():
            continue
        raw = "".join(ch for ch in ((row["first_name"] or "") + (row["last_name"] or "")) if ch.isascii() and (ch.isalnum() or ch == "_"))
        raw = raw or "user"
        base = (raw[:12] + "".join(ch for ch in (row["phone"] or "") if ch.isdigit())[-6:])[:20]
        if len(base) < 3:
            base = (base + "user")[:20]
        candidate = base
        n = 2
        while candidate.lower() in used_usernames:
            suffix = str(n)
            candidate = (base[:20-len(suffix)] + suffix)
            n += 1
        cursor.execute("UPDATE users SET username = ? WHERE id = ?", (candidate, row["id"]))
        used_usernames.add(candidate.lower())
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE)")
    except sqlite3.OperationalError:
        pass

    # Live customer-support inbox.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL CHECK(sender_type IN ('user','owner')),
            sender_id TEXT,
            message TEXT NOT NULL,
            reply_to_message_id INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES support_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(reply_to_message_id) REFERENCES support_messages(id) ON DELETE SET NULL
        )
    """)
    try:
        _ensure_column(cursor, "support_messages", "reply_to_message_id", "INTEGER")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_messages_conversation ON support_messages(conversation_id, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_messages_reply ON support_messages(reply_to_message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_conversations_last_message ON support_conversations(last_message_at DESC)")
    except sqlite3.OperationalError:
        pass

    # ========================================================
    # E-COMMERCE / CART / ORDERS / RECOVERY / SUPPORT MEDIA
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            payment_method TEXT NOT NULL DEFAULT 'seller_coordination',
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            subtotal INTEGER NOT NULL DEFAULT 0,
            shipping_cost INTEGER NOT NULL DEFAULT 0,
            total_amount INTEGER NOT NULL DEFAULT 0,
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            customer_email TEXT DEFAULT '',
            customer_address TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_title TEXT NOT NULL,
            unit_price INTEGER NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            weight TEXT DEFAULT '',
            line_total INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recovery_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            visitor_phone TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recovery_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL CHECK(sender_type IN ('user','owner')),
            sender_id TEXT DEFAULT '',
            message TEXT NOT NULL,
            reply_to_message_id INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES recovery_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(reply_to_message_id) REFERENCES recovery_messages(id) ON DELETE SET NULL
        )
    """)
# support media/edit columns
    try:
        _ensure_column(cursor, "support_messages", "attachment_path", "TEXT DEFAULT ''")
        _ensure_column(cursor, "support_messages", "attachment_type", "TEXT DEFAULT ''")
        _ensure_column(cursor, "support_messages", "attachment_paths", "TEXT DEFAULT '[]'")
        _ensure_column(cursor, "support_messages", "edited_at", "TEXT")
        _ensure_column(cursor, "support_messages", "deleted_at", "TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id, updated_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_status ON recovery_conversations(status, updated_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_messages_conv ON recovery_messages(conversation_id, id)")
    except sqlite3.OperationalError:
        pass

    # ========================================================
    # DEFAULT SITE SETTINGS
    # ========================================================

    count = cursor.execute("""
        SELECT COUNT(*)
        FROM site_settings
    """).fetchone()[0]

    if count == 0:

        cursor.execute("""
            INSERT INTO site_settings (

                site_name,

                site_tagline,

                welcome_text,

                about_text,

                support_text,

                contact_text,

                contact_title,

                contact_button_text,

                background_color,

                banner

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            "عسل شهدآور",

            "طعم واقعی طبیعت",

            "سلام دوست عزیز؛ به بهشت عسل شهدآور خوش اومدی!",

            "شهدآور با هدف عرضه محصولات طبیعی و اصیل زنبورداری فعالیت می‌کند.",

            "برای دریافت راهنمایی و پشتیبانی با ما در ارتباط باشید.",

            "برای خرید، مشاوره و دریافت اطلاعات محصولات با ما در ارتباط باشید.",

            "تماس با شهدآور",

            "تماس با ما",

            "#fffdf8",

            "",
        ))

    # ========================================================
    # DEFAULT CATEGORIES
    # ========================================================

    category_count = cursor.execute("""
        SELECT COUNT(*)
        FROM categories
    """).fetchone()[0]

    if category_count == 0:

        default_categories = [

            "عسل",

            "ژل رویال",

            "گرده گل",

            "محصولات زنبورداری",

        ]

        for category in default_categories:

            cursor.execute("""
                INSERT OR IGNORE INTO categories (
                    name
                )
                VALUES (?)
            """, (
                category,
            ))

    # ========================================================
    # NO DEFAULT CONTACT METHOD
    # ========================================================
    #
    # توجه:
    # در نسخه جدید عمداً هیچ INSERT برای contact_methods
    # انجام نمی‌شود.
    #
    # تا زمانی که مدیر سایت از پنل مالکیت راه ارتباطی
    # اضافه نکند، جدول contact_methods می‌تواند کاملاً
    # خالی باشد.
    #
    # ========================================================

    # ========================================================
    # KNOWLEDGE / PUBLIC PROFILES
    # ========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            category_id INTEGER,
            subtitle TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            content_html TEXT DEFAULT '',
            image TEXT DEFAULT '',
            gallery_json TEXT DEFAULT '[]',
            facts_json TEXT DEFAULT '[]',
            seo_title TEXT DEFAULT '',
            seo_description TEXT DEFAULT '',
            is_published INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(category_id) REFERENCES profile_categories(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT '',
            excerpt TEXT DEFAULT '',
            content_html TEXT DEFAULT '',
            cover_image TEXT DEFAULT '',
            seo_title TEXT DEFAULT '',
            seo_description TEXT DEFAULT '',
            is_published INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_category_order ON profiles(category_id, sort_order, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_published ON profiles(is_published, sort_order, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_published ON knowledge_articles(is_published, id)")
    except sqlite3.OperationalError:
        pass
    for table, cols in {
        'profiles': {
            'subtitle': "TEXT DEFAULT ''", 'summary': "TEXT DEFAULT ''", 'content_html': "TEXT DEFAULT ''",
            'image': "TEXT DEFAULT ''", 'gallery_json': "TEXT DEFAULT '[]'", 'facts_json': "TEXT DEFAULT '[]'",
            'seo_title': "TEXT DEFAULT ''", 'seo_description': "TEXT DEFAULT ''",
            'is_published': "INTEGER NOT NULL DEFAULT 1", 'sort_order': "INTEGER NOT NULL DEFAULT 0",
            'updated_at': "TEXT DEFAULT CURRENT_TIMESTAMP"
        },
        'knowledge_articles': {
            'category': "TEXT DEFAULT ''", 'excerpt': "TEXT DEFAULT ''", 'content_html': "TEXT DEFAULT ''",
            'cover_image': "TEXT DEFAULT ''", 'seo_title': "TEXT DEFAULT ''", 'seo_description': "TEXT DEFAULT ''",
            'is_published': "INTEGER NOT NULL DEFAULT 1", 'updated_at': "TEXT DEFAULT CURRENT_TIMESTAMP"
        }
    }.items():
        for col, definition in cols.items():
            try:
                _ensure_column(cursor, table, col, definition)
            except sqlite3.OperationalError:
                pass

    # Final commerce/support refinements: additive columns only; existing data is preserved.
    for table, columns in {
        'support_messages': {
            'is_pinned': "INTEGER NOT NULL DEFAULT 0",
            'order_id': "INTEGER",
        },
        'site_settings': {
            'support_profile_image': "TEXT DEFAULT ''",
            'support_background_image': "TEXT DEFAULT ''",
            'support_display_name': "TEXT DEFAULT 'پشتیبانی شهدآور'",
            'support_profile_text': "TEXT DEFAULT 'پاسخ‌گویی و هماهنگی سفارش‌های شهدآور'",
        },
    }.items():
        for col, definition in columns.items():
            try:
                _ensure_column(cursor, table, col, definition)
            except sqlite3.OperationalError:
                pass

    connection.commit()

    connection.close()


# ============================================================
# SITE SETTINGS
# ============================================================

def get_site_settings():

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM site_settings
        ORDER BY id
        LIMIT 1
    """).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else {}
    )


def update_site_setting(
    key,
    value,
):

    allowed = {

        "site_name",

        "site_tagline",

        "welcome_text",

        "about_text",

        "about_title",

        "about_image",

        "about_link",

        "support_text",

        "contact_text",

        "contact_title",

        "contact_button_text",

        "background_color",

        "banner",
        "support_profile_image",
        "support_background_image",
        "support_display_name",
        "support_profile_text",
    }

    if key not in allowed:

        return False

    connection = get_connection()

    try:

        row = connection.execute("""
            SELECT id
            FROM site_settings
            ORDER BY id
            LIMIT 1
        """).fetchone()

        if row:

            connection.execute(
                f"""
                UPDATE site_settings
                SET {key} = ?
                WHERE id = ?
                """,
                (
                    value,
                    row["id"],
                ),
            )

        else:

            connection.execute("""
                INSERT INTO site_settings (
                    site_name
                )
                VALUES (?)
            """, (
                "عسل شهدآور",
            ))

            row = connection.execute("""
                SELECT id
                FROM site_settings
                ORDER BY id
                LIMIT 1
            """).fetchone()

            connection.execute(
                f"""
                UPDATE site_settings
                SET {key} = ?
                WHERE id = ?
                """,
                (
                    value,
                    row["id"],
                ),
            )

        connection.commit()

        return True

    finally:

        connection.close()


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def update_site_settings(
    site_name,
    site_tagline,
    welcome_text,
    about_text,
    support_text,
    contact_text,
    background_color,
):

    update_site_setting(
        "site_name",
        site_name,
    )

    update_site_setting(
        "site_tagline",
        site_tagline,
    )

    update_site_setting(
        "welcome_text",
        welcome_text,
    )

    update_site_setting(
        "about_text",
        about_text,
    )

    update_site_setting(
        "support_text",
        support_text,
    )

    update_site_setting(
        "contact_text",
        contact_text,
    )

    update_site_setting(
        "background_color",
        background_color,
    )

    return True


# ============================================================
# CATEGORIES
# ============================================================

def get_categories():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM categories
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def create_category(
    name,
):

    connection = get_connection()

    try:

        connection.execute("""
            INSERT OR IGNORE INTO categories (
                name
            )
            VALUES (?)
        """, (
            name,
        ))

        connection.commit()

    finally:

        connection.close()


def add_category(
    name,
):

    create_category(
        name
    )


def update_category_cover(category_id, filename):
    connection = get_connection()
    try:
        connection.execute("UPDATE categories SET cover_image=? WHERE id=?", (filename or "", category_id))
        connection.commit()
        return True
    finally:
        connection.close()


def delete_category(
    category_id,
):

    connection = get_connection()

    connection.execute("""
        UPDATE products
        SET category_id = NULL
        WHERE category_id = ?
    """, (
        category_id,
    ))

    connection.execute("""
        DELETE FROM categories
        WHERE id = ?
    """, (
        category_id,
    ))

    connection.commit()

    connection.close()


# ============================================================
# PRODUCTS
# ============================================================

def _product_query():

    return """
        SELECT
            products.*,
            categories.name AS category_name
        FROM products
        LEFT JOIN categories
            ON products.category_id = categories.id
    """


def _normalize_product(
    row,
):

    if not row:
        return None

    product = dict(row)

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


def get_products(
    status=None,
):

    connection = get_connection()

    query = _product_query()

    params = []

    if status:

        query += """
            WHERE products.status = ?
        """

        params.append(
            status
        )

    query += """
        ORDER BY products.id DESC
    """

    rows = connection.execute(
        query,
        params,
    ).fetchall()

    connection.close()

    return [
        _normalize_product(row)
        for row in rows
    ]


def get_product(
    product_id,
):

    connection = get_connection()

    row = connection.execute(
        _product_query()
        + """
            WHERE products.id = ?
            LIMIT 1
        """,
        (
            product_id,
        ),
    ).fetchone()

    connection.close()

    return _normalize_product(
        row
    )


def create_product(
    title,
    price,
    description,
    category_id,
    status,
    discount_percent,
    final_price,
    discount_days,
    images,
    tags="",
    weight="",
    stock=0,
):

    discount_expires_at = None

    if (
        status == "discount"
        and discount_days
    ):

        try:

            days = int(
                discount_days
            )

            discount_expires_at = (
                datetime.now()
                + timedelta(
                    days=days
                )
            ).isoformat()

        except (
            ValueError,
            TypeError,
        ):

            discount_expires_at = None

    images = images or []

    image_1 = (
        images[0]
        if len(images) > 0
        else ""
    )

    image_2 = (
        images[1]
        if len(images) > 1
        else ""
    )

    image_3 = (
        images[2]
        if len(images) > 2
        else ""
    )

    connection = get_connection()

    cursor = connection.execute("""
        INSERT INTO products (

            title,

            price,

            description,

            category_id,

            status,

            discount_percent,

            final_price,

            discount_days,

            discount_expires_at,

            image_1,

            image_2,

            image_3,

            tags,

            weight,

            stock

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        title,

        price,

        description,

        category_id or None,

        status,

        discount_percent,

        final_price,

        discount_days or None,

        discount_expires_at,

        image_1,

        image_2,

        image_3,

        (tags or "").strip(),

        (weight or "").strip(),

        max(0, int(stock or 0)),
    ))

    connection.commit()

    product_id = cursor.lastrowid

    connection.close()

    return product_id


def add_product(
    title,
    price,
    description,
    category_id,
    image_1,
    image_2,
    image_3,
    status="normal",
    discount_percent=0,
    final_price=0,
    discount_days=0,
    is_discount=False,
    is_popular=False,
    is_available=True,
    tags="",
    weight="",
    stock=0,
):

    product_id = create_product(

        title=title,

        price=price,

        description=description,

        category_id=category_id,

        status=status,

        discount_percent=discount_percent,

        final_price=final_price,

        discount_days=discount_days,

        images=[

            image_1 or "",

            image_2 or "",

            image_3 or "",
        ],
        tags=tags,
        weight=weight,
        stock=stock,
    )

    connection = get_connection()

    connection.execute("""
        UPDATE products
        SET

            is_discount = ?,

            is_popular = ?,

            is_available = ?

        WHERE id = ?
    """, (

        1 if is_discount else 0,

        1 if is_popular else 0,

        1 if is_available else 0,

        product_id,
    ))

    connection.commit()

    connection.close()

    return product_id


def update_product(
    product_id,
    title,
    price,
    description,
    category_id,
    status,
    discount_percent,
    final_price,
    discount_days,
    new_images,
    tags=None,
    weight=None,
    stock=None,
):

    old_product = get_product(
        product_id
    )

    if not old_product:
        return False

    images = [

        old_product.get(
            "image_1",
            "",
        ),

        old_product.get(
            "image_2",
            "",
        ),

        old_product.get(
            "image_3",
            "",
        ),
    ]

    for index, image in enumerate(
        (new_images or [])[:3]
    ):

        images[index] = image

    discount_expires_at = None

    if (
        status == "discount"
        and discount_days
    ):

        try:

            days = int(
                discount_days
            )

            discount_expires_at = (
                datetime.now()
                + timedelta(
                    days=days
                )
            ).isoformat()

        except (
            ValueError,
            TypeError,
        ):

            discount_expires_at = None

    connection = get_connection()

    cursor = connection.execute("""
        UPDATE products
        SET

            title = ?,

            price = ?,

            description = ?,

            category_id = ?,

            status = ?,

            discount_percent = ?,

            final_price = ?,

            discount_days = ?,

            discount_expires_at = ?,

            image_1 = ?,

            image_2 = ?,

            image_3 = ?,

            tags = COALESCE(?, tags),

            weight = COALESCE(?, weight),

            stock = COALESCE(?, stock),

            updated_at = CURRENT_TIMESTAMP

        WHERE id = ?
    """, (

        title,

        price,

        description,

        category_id or None,

        status,

        discount_percent,

        final_price,

        discount_days or None,

        discount_expires_at,

        images[0],

        images[1],

        images[2],

        (tags or "").strip() if tags is not None else None,

        (weight or "").strip() if weight is not None else None,

        max(0, int(stock or 0)) if stock is not None else None,

        product_id,
    ))

    connection.commit()

    success = (
        cursor.rowcount > 0
    )

    connection.close()

    return success


def delete_product(
    product_id,
):

    connection = get_connection()

    connection.execute("""
        DELETE FROM products
        WHERE id = ?
    """, (
        product_id,
    ))

    connection.commit()

    connection.close()


def delete_product_image(
    product_id,
    image_number,
):

    allowed = {

        1: "image_1",

        2: "image_2",

        3: "image_3",
    }

    column = allowed.get(
        image_number
    )

    if not column:
        return False

    connection = get_connection()

    cursor = connection.execute(
        f"""
        UPDATE products
        SET {column} = ''
        WHERE id = ?
        """,
        (
            product_id,
        ),
    )

    connection.commit()

    success = (
        cursor.rowcount > 0
    )

    connection.close()

    return success


# ============================================================
# COVERS
# ============================================================

def get_covers():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM covers
        ORDER BY sort_order ASC, id ASC
    """).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_cover(
    cover_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM covers
        WHERE id = ?
    """, (
        cover_id,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def create_cover(
    filename,
    duration,
    sort_order=None,
):

    connection = get_connection()

    if sort_order is None:
        row = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM covers").fetchone()
        sort_order = int(row["n"])

    connection.execute("""
        INSERT INTO covers (
            filename,
            duration,
            sort_order
        )
        VALUES (?, ?, ?)
    """, (
        filename,
        duration,
        int(sort_order),
    ))

    connection.commit()

    connection.close()


def add_cover(
    filename,
    duration,
):

    create_cover(
        filename,
        duration,
    )


def update_cover(
    cover_id,
    filename,
    duration,
    sort_order=None,
):

    connection = get_connection()

    connection.execute("""
        UPDATE covers
        SET

            filename = ?,

            duration = ?,

            sort_order = COALESCE(?, sort_order)

        WHERE id = ?
    """, (

        filename,

        duration,

        sort_order,

        cover_id,
    ))

    connection.commit()

    connection.close()


def delete_cover(
    cover_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM covers
        WHERE id = ?
    """, (
        cover_id,
    )).fetchone()

    if row:

        connection.execute("""
            DELETE FROM covers
            WHERE id = ?
        """, (
            cover_id,
        ))

        connection.commit()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


# ============================================================
# LOGO
# ============================================================

def get_logo():

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM logo
        WHERE id = 1
    """).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def set_logo(
    filename,
):

    connection = get_connection()

    connection.execute("""
        INSERT INTO logo (
            id,
            filename
        )
        VALUES (1, ?)

        ON CONFLICT(id)

        DO UPDATE SET
            filename = excluded.filename
    """, (
        filename,
    ))

    connection.commit()

    connection.close()


def delete_logo():

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM logo
        WHERE id = 1
    """).fetchone()

    if row:

        connection.execute("""
            DELETE FROM logo
            WHERE id = 1
        """)

        connection.commit()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


# ============================================================
# BANNERS
# ============================================================

def get_banners():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM banners
        ORDER BY sort_order ASC, id ASC
    """).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_banner(
    banner_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM banners
        WHERE id = ?
        LIMIT 1
    """, (
        banner_id,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def add_banner(
    filename,
    title="",
    link="",
):
    connection = get_connection()
    try:
        row = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM banners").fetchone()
        sort_order = int(row["n"])
        cursor = connection.execute("""
            INSERT INTO banners (filename, title, link, is_active, sort_order)
            VALUES (?, ?, ?, 1, ?)
        """, (filename, title or "", link or "", sort_order))
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()



def update_banner(banner_id, filename, title="", link=""):
    connection = get_connection()
    try:
        cursor = connection.execute("UPDATE banners SET filename=?, title=?, link=? WHERE id=?", (filename, title or "", link or "", banner_id))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def toggle_banner(banner_id):
    connection = get_connection()
    try:
        cursor = connection.execute("UPDATE banners SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (banner_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def move_banner(banner_id, direction):
    if direction not in {"up", "down"}:
        return False
    connection = get_connection()
    try:
        rows = connection.execute("SELECT id, sort_order FROM banners ORDER BY sort_order ASC, id ASC").fetchall()
        index = next((i for i, row in enumerate(rows) if row["id"] == banner_id), None)
        if index is None:
            return False
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(rows):
            return False
        a, b = rows[index], rows[neighbor_index]
        connection.execute("UPDATE banners SET sort_order=? WHERE id=?", (b["sort_order"], a["id"]))
        connection.execute("UPDATE banners SET sort_order=? WHERE id=?", (a["sort_order"], b["id"]))
        connection.commit()
        return True
    finally:
        connection.close()

def delete_banner(
    banner_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM banners
        WHERE id = ?
        LIMIT 1
    """, (
        banner_id,
    )).fetchone()

    if row:

        connection.execute("""
            DELETE FROM banners
            WHERE id = ?
        """, (
            banner_id,
        ))

        connection.commit()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


# ============================================================
# CONTACT METHODS
# ============================================================

def _normalize_contact_method(
    row,
):

    if not row:
        return None

    contact = dict(row)

    # --------------------------------------------------------
    # سازگاری icon / icon_filename
    # --------------------------------------------------------

    if "icon" in contact:

        contact["icon_filename"] = (
            contact.get("icon") or ""
        )

    elif "icon_filename" not in contact:

        contact["icon_filename"] = ""

    # --------------------------------------------------------
    # مقادیر پیش‌فرض برای سازگاری با قالب‌های مختلف
    # --------------------------------------------------------

    if "icon_emoji" not in contact:

        contact["icon_emoji"] = ""

    if "icon_type" not in contact:
        contact["icon_type"] = "image" if contact.get("icon_filename") else "emoji"

    if "platform" not in contact:
        contact["platform"] = ""
    if "description" not in contact:
        contact["description"] = ""
    if "button_text" not in contact:
        contact["button_text"] = "ارتباط"

    # --------------------------------------------------------
    # تبدیل وضعیت به bool
    # --------------------------------------------------------

    contact["is_active"] = bool(
        contact.get(
            "is_active",
            1,
        )
    )

    return contact


def get_contact_methods(
    active_only=False,
):

    connection = get_connection()

    try:

        if active_only:

            rows = connection.execute("""
                SELECT *
                FROM contact_methods
                WHERE is_active = 1
                ORDER BY sort_order ASC, id ASC
            """).fetchall()

        else:

            rows = connection.execute("""
                SELECT *
                FROM contact_methods
                ORDER BY sort_order ASC, id ASC
            """).fetchall()

        return [
            _normalize_contact_method(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_contact_method(
    contact_id,
):

    connection = get_connection()

    try:

        row = connection.execute("""
            SELECT *
            FROM contact_methods
            WHERE id = ?
            LIMIT 1
        """, (
            contact_id,
        )).fetchone()

        return _normalize_contact_method(
            row
        )

    finally:

        connection.close()


def create_contact_method(
    title,
    value="",
    link="",
    icon="",
    is_active=True,
    sort_order=None,
    icon_filename=None,
    icon_emoji=None,
    icon_type="emoji",
    platform=None,
    description="",
    button_text="ارتباط",
):

    # --------------------------------------------------------
    # پشتیبانی از icon_filename
    # --------------------------------------------------------

    if icon_filename is not None:

        icon = icon_filename

    connection = get_connection()

    try:

        # ----------------------------------------------------
        # ترتیب خودکار
        # ----------------------------------------------------

        if sort_order is None:

            row = connection.execute("""
                SELECT
                    COALESCE(
                        MAX(sort_order),
                        -1
                    ) + 1 AS next_order
                FROM contact_methods
            """).fetchone()

            sort_order = row["next_order"]

        # ----------------------------------------------------
        # توجه:
        # جدول فعلی فقط icon را ذخیره می‌کند.
        #
        # icon_emoji و platform برای سازگاری API پذیرفته
        # می‌شوند ولی تا زمانی که ستون مربوطه در دیتابیس
        # وجود نداشته باشد، ذخیره نمی‌شوند.
        # ----------------------------------------------------

        cursor = connection.execute("""
            INSERT INTO contact_methods (

                title,

                value,

                link,

                icon,

                platform,

                icon_emoji,

                icon_type,

                description,

                button_text,

                is_active,

                sort_order

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            (title or "").strip(),

            (value or "").strip(),

            (link or "").strip(),

            (icon or "").strip(),

            (platform or "").strip(),

            (icon_emoji or "📞").strip(),

            (icon_type or ("image" if icon else "emoji")).strip(),

            (description or "").strip(),

            (button_text or "ارتباط").strip(),

            1 if is_active else 0,

            int(sort_order),
        ))

        connection.commit()

        return cursor.lastrowid

    finally:

        connection.close()


def update_contact_method(
    contact_id,
    title,
    value="",
    link="",
    icon=None,
    is_active=True,
    sort_order=None,
    icon_filename=None,
    icon_emoji=None,
    icon_type=None,
    platform=None,
    description=None,
    button_text=None,
):

    old = get_contact_method(
        contact_id
    )

    if not old:
        return False

    # --------------------------------------------------------
    # سازگاری icon_filename
    # --------------------------------------------------------

    if icon_filename is not None:

        icon = icon_filename

    if icon is None:

        icon = old.get(
            "icon",
            old.get(
                "icon_filename",
                "",
            ),
        )

    if sort_order is None:

        sort_order = old.get(
            "sort_order",
            0,
        )

    connection = get_connection()

    try:

        cursor = connection.execute("""
            UPDATE contact_methods

            SET

                title = ?,

                value = ?,

                link = ?,

                icon = ?,

                platform = ?,

                icon_emoji = ?,

                icon_type = ?,

                description = ?,

                button_text = ?,

                is_active = ?,

                sort_order = ?,

                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
        """, (

            (title or "").strip(),

            (value or "").strip(),

            (link or "").strip(),

            (icon or "").strip(),

            (platform if platform is not None else old.get("platform", "") or "").strip(),

            (icon_emoji if icon_emoji is not None else old.get("icon_emoji", "📞") or "📞").strip(),

            (icon_type if icon_type is not None else old.get("icon_type") or ("image" if icon else "emoji")).strip(),

            (description if description is not None else old.get("description", "") or "").strip(),

            (button_text if button_text is not None else old.get("button_text", "ارتباط") or "ارتباط").strip(),

            1 if is_active else 0,

            int(sort_order),

            contact_id,
        ))

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


def delete_contact_method(
    contact_id,
):

    connection = get_connection()

    try:

        row = connection.execute("""
            SELECT *
            FROM contact_methods
            WHERE id = ?
            LIMIT 1
        """, (
            contact_id,
        )).fetchone()

        if not row:

            return None

        connection.execute("""
            DELETE FROM contact_methods
            WHERE id = ?
        """, (
            contact_id,
        ))

        connection.commit()

        return _normalize_contact_method(
            row
        )

    finally:

        connection.close()


def toggle_contact_method(
    contact_id,
    is_active=None,
):

    connection = get_connection()

    try:

        if is_active is None:

            connection.execute("""
                UPDATE contact_methods

                SET

                    is_active =
                        CASE
                            WHEN is_active = 1
                            THEN 0
                            ELSE 1
                        END,

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
            """, (
                contact_id,
            ))

        else:

            connection.execute("""
                UPDATE contact_methods

                SET

                    is_active = ?,

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
            """, (
                1 if is_active else 0,

                contact_id,
            ))

        connection.commit()

        return True

    finally:

        connection.close()


def update_contact_order(
    contact_id,
    sort_order,
):

    connection = get_connection()

    try:

        cursor = connection.execute("""
            UPDATE contact_methods

            SET

                sort_order = ?,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
        """, (

            int(sort_order or 0),

            contact_id,
        ))

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


def move_contact_method(
    contact_id,
    direction,
):

    """
    جابه‌جایی ترتیب یک راه ارتباطی به بالا یا پایین.

    direction:
        "up"   -> انتقال به بالا
        "down" -> انتقال به پایین
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:

        current = cursor.execute(
            """
            SELECT
                id,
                sort_order
            FROM contact_methods
            WHERE id = ?
            """,
            (
                contact_id,
            ),
        ).fetchone()

        if not current:

            return False

        current_order = current["sort_order"]

        # ----------------------------------------------------
        # انتقال به بالا
        # ----------------------------------------------------

        if direction == "up":

            neighbor = cursor.execute(
                """
                SELECT
                    id,
                    sort_order
                FROM contact_methods
                WHERE sort_order < ?
                ORDER BY
                    sort_order DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    current_order,
                ),
            ).fetchone()

        # ----------------------------------------------------
        # انتقال به پایین
        # ----------------------------------------------------

        elif direction == "down":

            neighbor = cursor.execute(
                """
                SELECT
                    id,
                    sort_order
                FROM contact_methods
                WHERE sort_order > ?
                ORDER BY
                    sort_order ASC,
                    id ASC
                LIMIT 1
                """,
                (
                    current_order,
                ),
            ).fetchone()

        else:

            return False

        # ----------------------------------------------------
        # همسایه وجود ندارد
        # ----------------------------------------------------

        if not neighbor:

            return False

        neighbor_id = neighbor["id"]
        neighbor_order = neighbor["sort_order"]

        # ----------------------------------------------------
        # جابه‌جایی
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE contact_methods

            SET

                sort_order = ?,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                neighbor_order,
                contact_id,
            ),
        )

        cursor.execute(
            """
            UPDATE contact_methods

            SET

                sort_order = ?,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                current_order,
                neighbor_id,
            ),
        )

        connection.commit()

        return True

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# ============================================================
# USERS
# ============================================================

def create_user(
    first_name,
    last_name,
    phone,
    email,
    province,
    city,
    gender,
    password_hash,
    avatar="",
    terms_accepted=True,
    username="",
):

    connection = get_connection()

    try:

        cursor = connection.execute("""
            INSERT INTO users (

                first_name,

                last_name,

                phone,

                email,

                province,

                city,

                gender,

                password_hash,

                avatar,

                terms_accepted,

                username

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            first_name,

            last_name,

            phone,

            email or None,

            province or "",

            city or "",

            gender,

            password_hash or "",

            avatar or "",

            1 if terms_accepted else 0,

            username or "",
        ))

        connection.commit()

        return cursor.lastrowid

    finally:

        connection.close()


def get_user_by_phone(
    phone,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM users
        WHERE phone = ?
        LIMIT 1
    """, (
        phone,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def get_user_by_email(
    email,
):

    if not email:
        return None

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM users
        WHERE LOWER(email) = LOWER(?)
        LIMIT 1
    """, (
        email,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def get_user(
    user_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        LIMIT 1
    """, (
        user_id,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def get_user_by_id(
    user_id,
):

    return get_user(
        user_id
    )


def update_user(
    user_id,
    first_name,
    last_name,
    phone,
    email,
    province,
    city,
    gender,
    username=None,
):

    connection = get_connection()

    try:

        connection.execute("""
            UPDATE users

            SET

                first_name = ?,

                last_name = ?,

                phone = ?,

                email = ?,

                province = ?,

                city = ?,

                gender = ?,

                username = COALESCE(?, username),

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
        """, (

            first_name,

            last_name,

            phone,

            email or None,

            province,

            city,

            gender,

            username,

            user_id,
        ))

        connection.commit()

    finally:

        connection.close()


def update_user_password(
    user_id,
    password_hash,
):

    connection = get_connection()

    try:

        connection.execute("""
            UPDATE users

            SET

                password_hash = ?,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
        """, (

            password_hash,

            user_id,
        ))

        connection.commit()

    finally:

        connection.close()


def update_user_avatar(
    user_id,
    avatar,
):

    connection = get_connection()

    try:

        connection.execute("""
            UPDATE users

            SET

                avatar = ?,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
        """, (

            avatar,

            user_id,
        ))

        connection.commit()

    finally:

        connection.close()


def get_users():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM users
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_user_count():

    connection = get_connection()

    row = connection.execute("""
        SELECT COUNT(*) AS total
        FROM users
    """).fetchone()

    connection.close()

    return int(
        row["total"]
    )


# ============================================================
# REVIEWS
# ============================================================

def create_review(
    product_id,
    user_id,
    comment,
    rating=5,
):

    connection = get_connection()

    cursor = connection.execute("""
        INSERT INTO reviews (

            product_id,

            user_id,

            comment,

            rating,

            status

        )

        VALUES (?, ?, ?, ?, 'pending')
    """, (

        product_id,

        user_id,

        comment,

        max(1, min(5, int(rating or 5))),
    ))

    connection.commit()

    review_id = cursor.lastrowid

    connection.close()

    return review_id


def get_review(
    review_id,
):

    connection = get_connection()

    row = connection.execute("""
        SELECT

            reviews.*,

            products.title AS product_title,

            users.first_name,

            users.last_name,

            users.avatar,

            users.phone,

            users.gender,

            users.username

        FROM reviews

        INNER JOIN products
            ON reviews.product_id = products.id

        INNER JOIN users
            ON reviews.user_id = users.id

        WHERE reviews.id = ?
    """, (
        review_id,
    )).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def get_product_reviews(
    product_id,
    approved_only=True,
):

    connection = get_connection()

    if approved_only:

        rows = connection.execute("""
            SELECT

                reviews.*,

                users.first_name,

                users.last_name,

                users.avatar,

                users.username

            FROM reviews

            INNER JOIN users
                ON reviews.user_id = users.id

            WHERE reviews.product_id = ?

              AND reviews.status IN ('approved', 'replied')

            ORDER BY reviews.id DESC
        """, (
            product_id,
        )).fetchall()

    else:

        rows = connection.execute("""
            SELECT

                reviews.*,

                users.first_name,

                users.last_name,

                users.avatar,

                users.username

            FROM reviews

            INNER JOIN users
                ON reviews.user_id = users.id

            WHERE reviews.product_id = ?

            ORDER BY reviews.id DESC
        """, (
            product_id,
        )).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# AUTO INIT
# ============================================================

if __name__ == "__main__":

    init_db()

    print(
        "✅ پایگاه داده شهدآور با موفقیت آماده شد."
    )

# ============================================================
# USERNAME HELPERS
# ============================================================

def get_user_by_username(username):
    username = (username or "").strip()
    if not username:
        return None
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE LIMIT 1", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def is_username_available(username, exclude_user_id=None):
    username = (username or "").strip()
    if not username:
        return False
    connection = get_connection()
    try:
        if exclude_user_id:
            row = connection.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE AND id != ? LIMIT 1", (username, exclude_user_id)).fetchone()
        else:
            row = connection.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE LIMIT 1", (username,)).fetchone()
        return row is None
    finally:
        connection.close()


# ============================================================
# REVIEW MANAGEMENT
# ============================================================

def get_all_reviews(status=None):
    connection = get_connection()
    try:
        query = """
            SELECT reviews.*, products.title AS product_title,
                   users.first_name, users.last_name, users.avatar,
                   users.phone, users.gender, users.username
            FROM reviews
            JOIN products ON products.id = reviews.product_id
            JOIN users ON users.id = reviews.user_id
        """
        params = []
        if status:
            query += " WHERE reviews.status = ?"
            params.append(status)
        query += " ORDER BY CASE WHEN reviews.status = 'pending' THEN 0 ELSE 1 END, reviews.id DESC"
        return [dict(r) for r in connection.execute(query, params).fetchall()]
    finally:
        connection.close()


def get_pending_reviews_count():
    connection = get_connection()
    try:
        return int(connection.execute("SELECT COUNT(*) AS n FROM reviews WHERE status = 'pending'").fetchone()["n"])
    finally:
        connection.close()


def set_review_status(review_id, status):
    if status not in {"pending", "approved", "rejected", "replied"}:
        return False
    connection = get_connection()
    try:
        cur = connection.execute("UPDATE reviews SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, review_id))
        connection.commit()
        return cur.rowcount > 0
    finally:
        connection.close()


def set_review_reply(review_id, reply):
    connection = get_connection()
    try:
        cur = connection.execute("""
            UPDATE reviews
            SET owner_reply = ?, owner_reply_at = CASE WHEN ? != '' THEN CURRENT_TIMESTAMP ELSE NULL END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, ((reply or "").strip(), (reply or "").strip(), review_id))
        connection.commit()
        return cur.rowcount > 0
    finally:
        connection.close()


def delete_review(review_id):
    connection = get_connection()
    try:
        cur = connection.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        connection.commit()
        return cur.rowcount > 0
    finally:
        connection.close()


# ============================================================
# CUSTOMER SUPPORT
# ============================================================

def get_or_create_support_conversation(user_id):
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM support_conversations WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return dict(row)
        cur = connection.execute("INSERT INTO support_conversations (user_id) VALUES (?)", (user_id,))
        connection.commit()
        row = connection.execute("SELECT * FROM support_conversations WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        connection.close()


def get_support_conversations():
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT c.*, u.first_name, u.last_name, u.username, u.phone, u.avatar, u.gender,
                   (SELECT COUNT(*) FROM support_messages sm WHERE sm.conversation_id = c.id AND sm.sender_type = 'user' AND sm.is_read = 0) AS unread_count
            FROM support_conversations c
            JOIN users u ON u.id = c.user_id
            ORDER BY c.last_message_at DESC, c.id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        connection.close()


def get_support_conversation(conversation_id):
    connection = get_connection()
    try:
        row = connection.execute("""
            SELECT c.*, u.first_name, u.last_name, u.username, u.phone, u.avatar, u.gender
            FROM support_conversations c JOIN users u ON u.id = c.user_id
            WHERE c.id = ?
        """, (conversation_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_support_messages(conversation_id):
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT m.*, q.message AS reply_to_message,
                   o.order_number, o.payment_status AS order_payment_status,
                   o.status AS order_status, o.total_amount AS order_total,
                   o.payment_method AS order_payment_method
            FROM support_messages m
            LEFT JOIN support_messages q ON q.id = m.reply_to_message_id
            LEFT JOIN orders o ON o.id = m.order_id
            WHERE m.conversation_id = ?
            ORDER BY m.id ASC
        """, (conversation_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try: item["attachment_paths"] = json.loads(item.get("attachment_paths") or "[]")
            except Exception: item["attachment_paths"] = []
            if not item["attachment_paths"] and item.get("attachment_path"): item["attachment_paths"]=[item.get("attachment_path")]
            item["created_at_display"] = _support_time_display(item.get("created_at"))
            result.append(item)
        return result
    finally:
        connection.close()


def add_support_message(conversation_id, sender_type, sender_id, message, reply_to_message_id=None):
    message = (message or "").strip()
    if not message or sender_type not in {"user", "owner"}:
        return None
    connection = get_connection()
    try:
        if reply_to_message_id:
            valid_reply = connection.execute(
                "SELECT id FROM support_messages WHERE id = ? AND conversation_id = ?",
                (int(reply_to_message_id), conversation_id),
            ).fetchone()
            if not valid_reply:
                reply_to_message_id = None
        cur = connection.execute("""
            INSERT INTO support_messages (conversation_id, sender_type, sender_id, message, reply_to_message_id)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, sender_type, str(sender_id or ""), message, reply_to_message_id))
        connection.execute("""
            UPDATE support_conversations
            SET updated_at = CURRENT_TIMESTAMP, last_message_at = CURRENT_TIMESTAMP, status = 'open'
            WHERE id = ?
        """, (conversation_id,))
        connection.commit()
        return cur.lastrowid
    finally:
        connection.close()


def set_support_message_meta(message_id, *, is_pinned=None, order_id=None):
    connection = get_connection()
    try:
        fields=[]; params=[]
        if is_pinned is not None:
            fields.append("is_pinned=?"); params.append(1 if is_pinned else 0)
        if order_id is not None:
            fields.append("order_id=?"); params.append(order_id)
        if not fields:
            return False
        params.append(message_id)
        cur=connection.execute(f"UPDATE support_messages SET {', '.join(fields)} WHERE id=?", params)
        connection.commit(); return cur.rowcount>0
    finally:
        connection.close()


def pin_support_message(message_id, pinned=True):
    return set_support_message_meta(message_id, is_pinned=pinned)


def mark_support_messages_read(conversation_id, sender_type):
    connection = get_connection()
    try:
        connection.execute("UPDATE support_messages SET is_read = 1 WHERE conversation_id = ? AND sender_type = ?", (conversation_id, sender_type))
        connection.commit()
    finally:
        connection.close()


def get_unread_support_count():
    connection = get_connection()
    try:
        row = connection.execute("SELECT COUNT(*) AS n FROM support_messages WHERE sender_type = 'user' AND is_read = 0").fetchone()
        return int(row["n"])
    finally:
        connection.close()


# ============================================================
# CART / ORDERS
# ============================================================

def get_cart(user_id):
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT c.id AS cart_id, c.quantity, p.*, categories.name AS category_name
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            LEFT JOIN categories ON categories.id = p.category_id
            WHERE c.user_id = ?
            ORDER BY c.id DESC
        """, (user_id,)).fetchall()
        items=[]
        total=0
        for r in rows:
            item=dict(r)
            price=int(item.get('final_price') or item.get('price') or 0) if item.get('is_discount') else int(item.get('price') or 0)
            if item.get('is_discount') and not item.get('final_price'):
                price=int(item.get('price') or 0)
            item['unit_price']=price
            item['line_total']=price*int(item.get('quantity') or 0)
            total += item['line_total']
            items.append(item)
        return items, total
    finally:
        connection.close()


def upsert_cart_item(user_id, product_id, quantity):
    quantity=max(1,int(quantity or 1))
    connection=get_connection()
    try:
        product=connection.execute("SELECT id, is_available, stock FROM products WHERE id=?",(product_id,)).fetchone()
        if not product or not product['is_available']:
            return False, 'این محصول در حال حاضر قابل سفارش نیست.'
        stock=int(product['stock'] or 0)
        if stock and quantity>stock:
            quantity=stock
        connection.execute("""
            INSERT INTO cart_items(user_id,product_id,quantity) VALUES(?,?,?)
            ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=excluded.quantity, updated_at=CURRENT_TIMESTAMP
        """,(user_id,product_id,quantity))
        connection.commit()
        return True, quantity
    finally:
        connection.close()


def update_cart_quantity(user_id, product_id, quantity):
    quantity=int(quantity or 0)
    connection=get_connection()
    try:
        if quantity<=0:
            connection.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?",(user_id,product_id))
        else:
            product=connection.execute("SELECT stock,is_available FROM products WHERE id=?",(product_id,)).fetchone()
            if not product or not product['is_available']:
                connection.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?",(user_id,product_id))
            else:
                stock=int(product['stock'] or 0)
                if stock and quantity>stock: quantity=stock
                connection.execute("UPDATE cart_items SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND product_id=?",(quantity,user_id,product_id))
        connection.commit(); return True
    finally: connection.close()


def remove_cart_item(user_id, product_id):
    connection=get_connection()
    try:
        cur=connection.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?",(user_id,product_id)); connection.commit(); return cur.rowcount>0
    finally: connection.close()


def clear_cart(user_id):
    connection=get_connection()
    try:
        connection.execute("DELETE FROM cart_items WHERE user_id=?",(user_id,)); connection.commit()
    finally: connection.close()


def create_order_from_cart(user_id, payment_method, address='', notes=''):
    items, subtotal=get_cart(user_id)
    if not items: return None, 'سبد خرید خالی است.'
    user=get_user(user_id)
    if not user: return None, 'کاربر پیدا نشد.'
    order_number='SHD-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper()
    payment_method=payment_method if payment_method in {'seller_coordination','online'} else 'seller_coordination'
    payment_status='pending' if payment_method=='online' else 'unpaid'
    connection=get_connection()
    try:
        cur=connection.execute("""INSERT INTO orders(user_id,order_number,status,payment_method,payment_status,subtotal,total_amount,customer_name,customer_phone,customer_email,customer_address,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(user_id,order_number,'pending',payment_method,payment_status,subtotal,subtotal,f"{user.get('first_name','')} {user.get('last_name','')}",user.get('phone',''),user.get('email') or '',address or '',notes or ''))
        oid=cur.lastrowid
        for item in items:
            connection.execute("INSERT INTO order_items(order_id,product_id,product_title,unit_price,quantity,weight,line_total) VALUES(?,?,?,?,?,?,?)",(oid,item['id'],item['title'],item['unit_price'],item['quantity'],item.get('weight') or '',item['line_total']))
        connection.execute("DELETE FROM cart_items WHERE user_id=?",(user_id,))
        connection.commit(); return order_number, None
    finally: connection.close()


def get_user_orders(user_id):
    connection=get_connection()
    try:
        orders=[]
        for r in connection.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall():
            o=dict(r); o['items']=[dict(x) for x in connection.execute("SELECT oi.*, p.image_1, p.image_2, p.image_3 FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? ORDER BY oi.id",(r['id'],)).fetchall()]; orders.append(o)
        return orders
    finally: connection.close()


def get_order_by_number(order_number,user_id=None):
    connection=get_connection()
    try:
        q="SELECT * FROM orders WHERE order_number=?"; params=[order_number]
        if user_id is not None: q+=" AND user_id=?"; params.append(user_id)
        r=connection.execute(q,params).fetchone()
        if not r:return None
        o=dict(r); o['items']=[dict(x) for x in connection.execute("SELECT oi.*, p.image_1, p.image_2, p.image_3 FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? ORDER BY oi.id",(r['id'],)).fetchall()]; return o
    finally: connection.close()

# ============================================================
# RECOVERY CHAT
# ============================================================

def get_or_create_recovery_conversation(user_id=None, phone=''):
    connection=get_connection()
    try:
        if user_id:
            r=connection.execute("SELECT * FROM recovery_conversations WHERE user_id=? ORDER BY id DESC LIMIT 1",(user_id,)).fetchone()
            if r:return dict(r)
        cur=connection.execute("INSERT INTO recovery_conversations(user_id,visitor_phone) VALUES(?,?)",(user_id,phone or ''))
        connection.commit(); return dict(connection.execute("SELECT * FROM recovery_conversations WHERE id=?",(cur.lastrowid,)).fetchone())
    finally: connection.close()


def get_recovery_conversations():
    connection=get_connection()
    try:
        rows=connection.execute("""SELECT c.*,u.first_name,u.last_name,u.username,u.phone,u.avatar,(SELECT COUNT(*) FROM recovery_messages m WHERE m.conversation_id=c.id AND m.sender_type='user' AND m.is_read=0) unread_count FROM recovery_conversations c LEFT JOIN users u ON u.id=c.user_id ORDER BY c.updated_at DESC,c.id DESC""").fetchall(); return [dict(r) for r in rows]
    finally: connection.close()


def get_recovery_messages(conversation_id):
    connection=get_connection()
    try:
        rows=connection.execute("SELECT m.*,q.message reply_to_message FROM recovery_messages m LEFT JOIN recovery_messages q ON q.id=m.reply_to_message_id WHERE m.conversation_id=? ORDER BY m.id",(conversation_id,)).fetchall(); return [dict(r) for r in rows]
    finally: connection.close()


def add_recovery_message(conversation_id,sender_type,sender_id,message,reply_to_message_id=None):
    message=(message or '').strip()
    if not message or sender_type not in {'user','owner'}: return None
    connection=get_connection()
    try:
        cur=connection.execute("INSERT INTO recovery_messages(conversation_id,sender_type,sender_id,message,reply_to_message_id) VALUES(?,?,?,?,?)",(conversation_id,sender_type,str(sender_id or ''),message,reply_to_message_id)); connection.execute("UPDATE recovery_conversations SET updated_at=CURRENT_TIMESTAMP,status='open' WHERE id=?",(conversation_id,)); connection.commit(); return cur.lastrowid
    finally: connection.close()


def mark_recovery_read(conversation_id,sender_type):
    connection=get_connection()
    try: connection.execute("UPDATE recovery_messages SET is_read=1 WHERE conversation_id=? AND sender_type=?",(conversation_id,sender_type)); connection.commit()
    finally: connection.close()


def get_unread_recovery_count():
    connection=get_connection()
    try: return int(connection.execute("SELECT COUNT(*) n FROM recovery_messages WHERE sender_type='user' AND is_read=0").fetchone()['n'])
    finally: connection.close()


def delete_recovery_conversation(conversation_id):
    connection=get_connection()
    try: cur=connection.execute("DELETE FROM recovery_conversations WHERE id=?",(conversation_id,)); connection.commit(); return cur.rowcount>0
    finally: connection.close()


def update_support_message(message_id, sender_type, sender_id, message):
    connection=get_connection()
    try:
        cur=connection.execute("UPDATE support_messages SET message=?,edited_at=CURRENT_TIMESTAMP WHERE id=? AND sender_type=? AND sender_id=? AND deleted_at IS NULL",((message or '').strip(),message_id,sender_type,str(sender_id)));connection.commit();return cur.rowcount>0
    finally: connection.close()


def delete_support_message(message_id, sender_type, sender_id):
    connection=get_connection()
    try:
        cur=connection.execute("UPDATE support_messages SET message='پیام حذف شد.',deleted_at=CURRENT_TIMESTAMP WHERE id=? AND sender_type=? AND sender_id=?",(message_id,sender_type,str(sender_id)));connection.commit();return cur.rowcount>0
    finally: connection.close()


def get_recovery_conversation(conversation_id):
    connection=get_connection()
    try:
        row=connection.execute("SELECT * FROM recovery_conversations WHERE id=?",(conversation_id,)).fetchone(); return dict(row) if row else None
    finally: connection.close()


def get_all_orders():
    connection=get_connection()
    try:
        rows=connection.execute("""SELECT o.*,u.first_name,u.last_name,u.username,u.phone FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC""").fetchall(); result=[]
        for r in rows:
            o=dict(r);o['items']=[dict(x) for x in connection.execute("SELECT oi.*, p.image_1, p.image_2, p.image_3 FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? ORDER BY oi.id",(r['id'],)).fetchall()];result.append(o)
        return result
    finally: connection.close()


def get_order_by_id(order_id, user_id=None):
    connection=get_connection()
    try:
        q="SELECT * FROM orders WHERE id=?"; params=[order_id]
        if user_id is not None: q += " AND user_id=?"; params.append(user_id)
        r=connection.execute(q,params).fetchone()
        if not r:return None
        o=dict(r); o['items']=[dict(x) for x in connection.execute("SELECT oi.*, p.image_1, p.image_2, p.image_3 FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? ORDER BY oi.id",(r['id'],)).fetchall()]; return o
    finally: connection.close()


def update_order_status(order_id,status,payment_status=None):
    allowed={'pending','processing','confirmed','shipped','completed','cancelled'}
    if status not in allowed:return False
    connection=get_connection()
    try:
        if payment_status is None:
            cur=connection.execute("UPDATE orders SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,order_id))
        else:
            cur=connection.execute("UPDATE orders SET status=?,payment_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,payment_status,order_id))
        connection.commit();return cur.rowcount>0
    finally: connection.close()

# ============================================================
# PUBLIC PROFILES / KNOWLEDGE API
# ============================================================

def get_profile_categories():
    connection = get_connection()
    try:
        return [dict(r) for r in connection.execute("SELECT * FROM profile_categories ORDER BY name COLLATE NOCASE").fetchall()]
    finally:
        connection.close()


def create_profile_category(name, slug):
    connection = get_connection()
    try:
        cur = connection.execute("INSERT INTO profile_categories(name,slug) VALUES(?,?)", (name.strip(), slug.strip()))
        connection.commit()
        return cur.lastrowid
    finally:
        connection.close()


def get_profile_category(category_id):
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM profile_categories WHERE id=?", (category_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def create_profile(data):
    connection = get_connection()
    try:
        cur = connection.execute("""INSERT INTO profiles(title,slug,category_id,subtitle,summary,content_html,image,gallery_json,facts_json,seo_title,seo_description,is_published,sort_order)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            data.get('title',''), data.get('slug',''), data.get('category_id') or None, data.get('subtitle',''), data.get('summary',''),
            data.get('content_html',''), data.get('image',''), data.get('gallery_json','[]'), data.get('facts_json','[]'),
            data.get('seo_title',''), data.get('seo_description',''), int(bool(data.get('is_published',1))), int(data.get('sort_order') or 0)
        ))
        connection.commit(); return cur.lastrowid
    finally: connection.close()


def update_profile(profile_id, data):
    connection = get_connection()
    try:
        cur = connection.execute("""UPDATE profiles SET title=?,slug=?,category_id=?,subtitle=?,summary=?,content_html=?,image=?,gallery_json=?,facts_json=?,seo_title=?,seo_description=?,is_published=?,sort_order=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (
            data.get('title',''), data.get('slug',''), data.get('category_id') or None, data.get('subtitle',''), data.get('summary',''),
            data.get('content_html',''), data.get('image',''), data.get('gallery_json','[]'), data.get('facts_json','[]'),
            data.get('seo_title',''), data.get('seo_description',''), int(bool(data.get('is_published',1))), int(data.get('sort_order') or 0), profile_id
        ))
        connection.commit(); return cur.rowcount > 0
    finally: connection.close()


def delete_profile(profile_id):
    connection = get_connection()
    try:
        cur = connection.execute("DELETE FROM profiles WHERE id=?", (profile_id,)); connection.commit(); return cur.rowcount > 0
    finally: connection.close()


def get_profiles(published_only=False, category_id=None):
    connection = get_connection()
    try:
        q="""SELECT p.*, c.name AS category_name, c.slug AS category_slug FROM profiles p LEFT JOIN profile_categories c ON c.id=p.category_id WHERE 1=1"""
        params=[]
        if published_only: q += " AND p.is_published=1"
        if category_id: q += " AND p.category_id=?"; params.append(category_id)
        q += " ORDER BY p.sort_order ASC, p.id DESC"
        rows=[dict(r) for r in connection.execute(q,params).fetchall()]
        return rows
    finally: connection.close()


def get_profile(profile_id, published_only=False):
    connection = get_connection()
    try:
        q="SELECT p.*, c.name AS category_name, c.slug AS category_slug FROM profiles p LEFT JOIN profile_categories c ON c.id=p.category_id WHERE p.id=?"
        params=[profile_id]
        if published_only: q += " AND p.is_published=1"
        row=connection.execute(q,params).fetchone(); return dict(row) if row else None
    finally: connection.close()


def get_profile_by_slug(slug, published_only=True):
    connection=get_connection()
    try:
        q="SELECT p.*, c.name AS category_name, c.slug AS category_slug FROM profiles p LEFT JOIN profile_categories c ON c.id=p.category_id WHERE p.slug=?"
        if published_only:q+=" AND p.is_published=1"
        row=connection.execute(q,(slug,)).fetchone(); return dict(row) if row else None
    finally: connection.close()


def create_knowledge_article(data):
    connection=get_connection()
    try:
        cur=connection.execute("""INSERT INTO knowledge_articles(title,slug,category,excerpt,content_html,cover_image,seo_title,seo_description,is_published)
            VALUES(?,?,?,?,?,?,?,?,?)""",(data.get('title',''),data.get('slug',''),data.get('category',''),data.get('excerpt',''),data.get('content_html',''),data.get('cover_image',''),data.get('seo_title',''),data.get('seo_description',''),int(bool(data.get('is_published',1)))))
        connection.commit(); return cur.lastrowid
    finally: connection.close()


def update_knowledge_article(article_id,data):
    connection=get_connection()
    try:
        cur=connection.execute("""UPDATE knowledge_articles SET title=?,slug=?,category=?,excerpt=?,content_html=?,cover_image=?,seo_title=?,seo_description=?,is_published=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",(data.get('title',''),data.get('slug',''),data.get('category',''),data.get('excerpt',''),data.get('content_html',''),data.get('cover_image',''),data.get('seo_title',''),data.get('seo_description',''),int(bool(data.get('is_published',1))),article_id))
        connection.commit(); return cur.rowcount>0
    finally: connection.close()


def delete_knowledge_article(article_id):
    connection=get_connection()
    try:
        cur=connection.execute("DELETE FROM knowledge_articles WHERE id=?",(article_id,));connection.commit();return cur.rowcount>0
    finally: connection.close()


def get_knowledge_articles(published_only=False):
    connection=get_connection()
    try:
        q="SELECT * FROM knowledge_articles"
        if published_only:q+=" WHERE is_published=1"
        q+=" ORDER BY id DESC"
        return [dict(r) for r in connection.execute(q).fetchall()]
    finally: connection.close()


def get_knowledge_article(article_id,published_only=False):
    connection=get_connection()
    try:
        q="SELECT * FROM knowledge_articles WHERE id=?";params=[article_id]
        if published_only:q+=" AND is_published=1"
        row=connection.execute(q,params).fetchone();return dict(row) if row else None
    finally: connection.close()


def get_knowledge_article_by_slug(slug,published_only=True):
    connection=get_connection()
    try:
        q="SELECT * FROM knowledge_articles WHERE slug=?";params=[slug]
        if published_only:q+=" AND is_published=1"
        row=connection.execute(q,params).fetchone();return dict(row) if row else None
    finally: connection.close()


def update_support_message_as_owner(message_id, message):
    connection=get_connection()
    try:
        cur=connection.execute("UPDATE support_messages SET message=?,edited_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL",((message or '').strip(),message_id))
        connection.commit();return cur.rowcount>0
    finally:connection.close()


def delete_support_message_as_owner(message_id):
    connection=get_connection()
    try:
        cur=connection.execute("UPDATE support_messages SET message='پیام حذف شد.',deleted_at=CURRENT_TIMESTAMP,attachment_path='',attachment_type='' WHERE id=?",(message_id,))
        connection.commit();return cur.rowcount>0
    finally:connection.close()
