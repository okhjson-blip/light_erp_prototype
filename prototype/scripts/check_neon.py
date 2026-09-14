from sqlalchemy import text
from app.database import get_conn, engine, init_db

print("dialect", engine.dialect.name)
print("connecting...")
conn = get_conn()
print("select1", conn.execute(text("SELECT 1")).scalar())
print(
    "public_tables",
    conn.execute(
        text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )
    ).scalar(),
)
print(
    "admin",
    conn.execute(
        text("SELECT email FROM app_user WHERE email=:e"),
        {"e": "admin@standard-erp.local"},
    ).scalar(),
)
conn.close()
print("init_db...")
print("is_new", init_db())
print("done")
