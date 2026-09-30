"""Read-only project audit plus isolated DB smoke tests for Shahdavar."""
from __future__ import annotations

import ast
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_python():
    for path in [ROOT / "app.py", ROOT / "database.py", ROOT / "services" / "shahdyar_service.py"]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("[PASS] Python AST/syntax")


def check_templates():
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        print("[SKIP] Jinja2 is not installed")
        return
    for directory in ("templates", "pages"):
        env = Environment(loader=FileSystemLoader(ROOT / directory))
        for path in (ROOT / directory).glob("*.html"):
            env.get_template(path.name)
    print("[PASS] Jinja templates")


def check_endpoints():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    endpoints = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "route":
                    endpoints.add(node.name)
    refs = set()
    for path in (ROOT / "templates").glob("*.html"):
        refs.update(re.findall(r"url_for\(\s*['\"]([^'\"]+)", path.read_text(encoding="utf-8")))
    missing = sorted(x for x in refs if x not in endpoints and x not in {"css_files", "js_files", "images", "uploads", "uploaded_file"})
    if missing:
        raise AssertionError(f"Missing endpoints: {missing}")
    print("[PASS] Template endpoint references")


def check_db():
    import sys
    sys.path.insert(0, str(ROOT))
    import database
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "honeyshop.db"
        shutil.copy2(ROOT / "honeyshop.db", db_path)
        database.DATABASE_PATH = db_path
        database.init_db()
        assert database.is_username_available("audit_user88")
        uid = database.create_user("Audit", "User", "09123456789", None, "لرستان", "بروجرد", "male", "hash", "male/male-01.png", True, "audit_user88")
        rid = database.create_review(1, uid, "audit review", 4)
        assert database.get_review(rid)["rating"] == 4
        conv = database.get_or_create_support_conversation(uid)
        m1 = database.add_support_message(conv["id"], "user", uid, "first")
        m2 = database.add_support_message(conv["id"], "owner", "owner", "reply", m1)
        assert database.get_support_messages(conv["id"])[-1]["reply_to_message_id"] == m1
        assert m2
        con = sqlite3.connect(db_path)
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.close()
    print("[PASS] Isolated database smoke test")


if __name__ == "__main__":
    check_python()
    check_templates()
    check_endpoints()
    check_db()
    print("Audit completed.")
