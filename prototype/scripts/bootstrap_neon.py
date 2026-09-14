"""One-shot Neon bootstrap: migrate + seed + report demo users."""
from sqlalchemy import text, inspect

from app.database import DATABASE_URL, IS_SQLITE, init_db, get_conn, engine
from app.seed import run_seed, _seed_common_mdm

print("dialect=", engine.dialect.name)
print("is_sqlite=", IS_SQLITE)
print("url_host=", DATABASE_URL.split("@")[-1].split("/")[0])

is_new = init_db()
print("is_new=", is_new)

if is_new:
    run_seed()
    print("seed_done")
else:
    conn = get_conn()
    try:
        admin_count = conn.execute(
            text("SELECT count(*) AS c FROM app_user WHERE email=:e"),
            {"e": "admin@standard-erp.local"},
        ).mappings().fetchone()["c"]
        print("admin_count=", admin_count)
        user_count = conn.execute(text("SELECT count(*) AS c FROM app_user")).mappings().fetchone()["c"]
        if user_count == 0:
            _seed_common_mdm(conn)
            conn.commit()
            print("demo_users_seeded")
    finally:
        conn.close()

insp = inspect(engine)
print("tables=", len(insp.get_table_names()))

conn = get_conn()
try:
    users = conn.execute(text("SELECT email FROM app_user ORDER BY user_id")).fetchall()
    print("users=", [u[0] for u in users])
finally:
    conn.close()

print("OK")
