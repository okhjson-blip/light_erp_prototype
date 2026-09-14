# 실행 환경변수로 전달된 통합 관리 계정을 안전하게 준비한다.
import os

from .auth import hash_password
from .database import get_conn, insert_returning, one, run


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f'{name} 환경변수가 필요합니다.')
    return value


def main() -> None:
    email = _required_env('AX_PORTAL_ADMIN_EMAIL')
    password = _required_env('AX_PORTAL_ADMIN_PASSWORD')
    conn = get_conn()
    try:
        role = one(run(conn, 'SELECT role_id FROM role WHERE name=?', ('관리자',)))
        if role is None:
            raise SystemExit('관리자 역할을 찾을 수 없습니다. 데이터베이스 초기화를 먼저 실행하세요.')

        user = one(run(conn, 'SELECT user_id FROM app_user WHERE email=?', (email,)))
        password_hash = hash_password(password)
        if user is None:
            user_id = insert_returning(
                conn,
                'INSERT INTO app_user (name, email, password_hash) VALUES (?,?,?)',
                ('AX Platform 관리자', email, password_hash),
                'user_id',
            )
        else:
            user_id = user['user_id']
            run(
                conn,
                'UPDATE app_user SET name=?, password_hash=? WHERE user_id=?',
                ('AX Platform 관리자', password_hash, user_id),
            )

        assigned = one(run(
            conn,
            'SELECT 1 FROM user_role WHERE user_id=? AND role_id=?',
            (user_id, role['role_id']),
        ))
        if assigned is None:
            run(conn, 'INSERT INTO user_role (user_id, role_id) VALUES (?,?)', (user_id, role['role_id']))
        conn.commit()
    finally:
        conn.close()
    print('통합 관리 계정을 준비했습니다.')


if __name__ == '__main__':
    main()
