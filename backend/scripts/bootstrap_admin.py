from __future__ import annotations

import argparse
import os
import sys

from audit.service import security_audit_service
from auth.providers.local import LocalPasswordService
from auth.rbac import Role
from database import SessionLocal, verify_database_ready
from models.auth import IdentityProvider, RoleBinding, UserAccount


PASSWORD_ENV = "BOOTSTRAP_ADMIN_PASSWORD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the first local AgenticOps administrator")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--email")
    parser.add_argument("--confirm-create-first-admin", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_create_first_admin:
        print("Refusing bootstrap without --confirm-create-first-admin", file=sys.stderr)
        return 2
    password = os.getenv(PASSWORD_ENV, "")
    if not password:
        print(f"{PASSWORD_ENV} must be supplied through the process environment", file=sys.stderr)
        return 2
    verify_database_ready()
    password_hash = LocalPasswordService().hash_password(password)
    db = SessionLocal()
    try:
        if db.query(UserAccount.id).first() is not None:
            print("Refusing bootstrap because at least one user already exists", file=sys.stderr)
            return 3
        provider = (
            db.query(IdentityProvider)
            .filter(IdentityProvider.provider_key == "local")
            .first()
        )
        if provider is None:
            provider = IdentityProvider(
                provider_key="local",
                provider_type="local",
                display_name="Local emergency login",
                enabled=True,
                config={},
                secrets_encrypted={},
                group_role_mapping={},
            )
            db.add(provider)
            db.flush()
        else:
            provider.enabled = True
        user = UserAccount(
            username=args.username.strip(),
            display_name=args.display_name.strip(),
            email=args.email,
            active=True,
            is_emergency=True,
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        db.add(RoleBinding(user_id=user.id, role=Role.ADMIN.value, source="bootstrap", provider_id=None))
        security_audit_service.append(
            db,
            event_type="auth.bootstrap_admin.created",
            outcome="success",
            actor_user_id=int(user.id),
            target_type="user_account",
            target_id=str(user.id),
            details={"username": user.username, "provider_key": provider.provider_key},
        )
        db.commit()
        print(f"Created local emergency administrator: {user.username}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
