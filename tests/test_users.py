import io
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from core import Base, get_db, setting
from users.userRouter import router
from users.profileRouter import router as profile_router
from users.models import UserModel, AuthSession, RefreshCredential
from users.auth.jwt_auth import create_access_token, utcnow, decode_claims
from users import profileService
import tasks.models
import categories.models


class UsersTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.include_router(profile_router)
        def database():
            with Session(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def register(self, username="Example", password=" Abcdef12 "):
        return self.client.post("/users/register", json={
            "username": username, "email": username.lower() + "@example.com",
            "password": password, "re_password": password,
        })

    def login(self, username="Example", password=" Abcdef12 ", client=None):
        return (client or self.client).post("/users/login", data={"username": username, "password": password})

    def csrf(self):
        return {"X-CSRF-Token": self.client.cookies.get("csrf_token")}

    def authenticated(self):
        self.assertEqual(self.register().status_code, 201)
        result = self.login()
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_register_optional_phone_role_and_exact_password(self):
        self.assertEqual(self.register().json()["role"], "user")
        self.assertEqual(self.register("Second").status_code, 201)
        self.assertEqual(self.register().status_code, 409)
        self.assertEqual(self.login(password="Abcdef12").status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_second_login_rejected_and_logout_allows_new_login(self):
        tokens = self.authenticated()
        self.assertEqual(self.login().status_code, 409)
        self.assertEqual(self.client.post("/users/logout", headers=self.csrf()).status_code, 200)
        result = self.client.get("/profile/my-profile", headers={"Authorization": "Bearer " + tokens["access_token"]})
        self.assertEqual(result.status_code, 401)
        self.assertEqual(self.client.post("/users/token/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_refresh_cannot_be_used_as_access(self):
        tokens = self.authenticated()
        result = self.client.get("/profile/my-profile", headers={"Authorization": "Bearer " + tokens["refresh_token"]})
        self.assertEqual(result.status_code, 401)

    def test_rotation_replay_revokes_session(self):
        tokens = self.authenticated()
        result = self.client.post("/users/token/refresh", headers=self.csrf())
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotEqual(tokens["refresh_token"], result.json()["refresh_token"])
        with Session(self.engine) as db:
            records = db.scalars(select(RefreshCredential)).all()
            self.assertEqual(len(records), 2)
            self.assertTrue(any(r.consumed_at is not None for r in records))
            self.assertTrue(all(r.token_hash != tokens["refresh_token"] for r in records))
        with TestClient(self.app, base_url="https://testserver") as other:
            replay = other.post("/users/token/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(self.client.get("/profile/my-profile").status_code, 401)

    def test_password_change_revokes_tokens(self):
        tokens = self.authenticated()
        data = {"old_password": " Abcdef12 ", "new_password": "NewPassword123", "re_new_password": "NewPassword123"}
        self.assertEqual(self.client.post("/users/change-password", json=data).status_code, 403)
        self.assertEqual(self.client.post("/users/change-password", json=data, headers=self.csrf()).status_code, 200)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.client.get("/profile/my-profile", headers={"Authorization": "Bearer " + tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.login(password="NewPassword123").status_code, 200)

    def test_wrong_old_password_does_not_revoke(self):
        self.authenticated()
        data = {"old_password": "WrongPass123", "new_password": "NewPassword123", "re_new_password": "NewPassword123"}
        self.assertEqual(self.client.post("/users/change-password", json=data, headers=self.csrf()).status_code, 400)
        self.assertEqual(self.client.get("/profile/my-profile").status_code, 404)

    def test_inactive_and_deleted_users_cannot_login_or_refresh(self):
        tokens = self.authenticated()
        with Session(self.engine) as db:
            user = db.scalar(select(UserModel))
            user.is_active = False
            db.commit()
        self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.client.post("/users/token/refresh", headers=self.csrf()).status_code, 403)
        with Session(self.engine) as db:
            user = db.scalar(select(UserModel))
            user.is_active = True
            user.is_delete = True
            db.commit()
        self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.client.get("/profile/my-profile").status_code, 403)

    def test_cookie_flags_csrf_and_origin(self):
        self.register()
        self.assertEqual(self.client.post("/users/login", data={"username":"Example","password":" Abcdef12 "},
                                         headers={"Origin":"https://evil.example"}).status_code, 403)
        response = self.login()
        cookies = response.headers.get_list("set-cookie")
        self.assertTrue(all("Secure" in c and "SameSite=lax" in c for c in cookies))
        self.assertTrue(all("HttpOnly" in c for c in cookies if not c.startswith("csrf_token=")))
        self.assertEqual(self.client.post("/users/token/refresh").status_code, 403)
        self.assertEqual(self.client.post("/users/logout").status_code, 403)

    def test_expired_session_allows_login(self):
        self.authenticated()
        with Session(self.engine) as db:
            db.scalar(select(AuthSession)).expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/profile/my-profile").status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_logout_with_expired_access_and_valid_refresh(self):
        tokens = self.authenticated()
        claims = decode_claims(tokens["access_token"])
        expired = create_access_token(int(claims["sub"]), claims["sid"], utcnow()-timedelta(seconds=5))
        self.client.cookies.set("access_token", expired, domain="testserver.local", path="/")
        self.assertEqual(self.client.post("/users/logout", headers=self.csrf()).status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_database_rejects_two_active_sessions(self):
        self.authenticated()
        with Session(self.engine) as db:
            existing = db.scalar(select(AuthSession))
            db.add(AuthSession(id="other", user_id_fk=existing.user_id_fk, created_at=utcnow(),
                               expires_at=existing.expires_at, csrf_hash="x"*64))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

    def test_profile_nullable_gender_website_and_own_national_id(self):
        self.authenticated()
        data = {"first_name":"Farid", "last_name":"Example", "national_id":"1234567890", "website":"https://example.com"}
        result = self.client.post("/profile/my-profile", json=data, headers=self.csrf())
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["website"], "https://example.com/")
        self.assertIsNone(result.json()["gender"])
        self.assertEqual(self.client.patch("/profile/my-profile", json={"national_id":"1234567890"}, headers=self.csrf()).status_code, 200)
        self.assertEqual(self.client.patch("/profile/my-profile", json={"bio":"Updated"}, headers=self.csrf()).status_code, 200)
        self.assertEqual(self.client.get("/profile/my-profile").status_code, 200)

    def test_first_avatar_then_complete_profile(self):
        self.authenticated()
        image = io.BytesIO()
        Image.new("RGB", (10,10)).save(image, format="PNG")
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)/"src"/"core"
            with patch.object(profileService, "BASE_DIR", base):
                result = self.client.post("/profile/avatar", files={"data":("photo.png",image.getvalue(),"image/png")}, headers=self.csrf())
                self.assertEqual(result.status_code, 201, result.text)
                files = list((Path(root)/"uploads"/"profiles").iterdir())
                self.assertEqual(files[0].suffix, ".png")
                data = {"first_name":"Farid", "last_name":"Example", "national_id":"1234567890"}
                self.assertEqual(self.client.post("/profile/my-profile", json=data, headers=self.csrf()).status_code, 201)

    def test_legacy_login_alias_uses_same_session_rules(self):
        self.register()
        result = self.client.post("/users/login2", data={"username":"Example","password":" Abcdef12 "})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.login().status_code, 409)


    def test_json_refresh_stays_json_across_repeated_requests(self):
        tokens = self.authenticated()
        with TestClient(self.app, base_url="https://testserver") as other:
            for _ in range(2):
                result = other.post("/users/token/refresh", json={"refresh_token": tokens["refresh_token"]})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.headers.get_list("set-cookie"), [])
                self.assertEqual(result.headers["cache-control"], "no-store")
                self.assertEqual(len(other.cookies), 0)
                tokens = result.json()

    def test_logout_falls_back_to_access_without_bypassing_csrf(self):
        tokens = self.authenticated()
        self.client.cookies.set("refresh_token", "invalid", domain="testserver.local", path="/")
        self.assertEqual(self.client.post("/users/logout").status_code, 403)
        with Session(self.engine) as db:
            self.assertIsNone(db.scalar(select(AuthSession)).revoked_at)
        self.assertEqual(self.client.post("/users/logout", headers=self.csrf()).status_code, 200)
        with Session(self.engine) as db:
            self.assertIsNotNone(db.scalar(select(AuthSession)).revoked_at)
        self.assertEqual(self.client.get("/profile/my-profile", headers={"Authorization": "Bearer " + tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_numeric_username_can_log_in(self):
        self.assertEqual(self.register("09123456789").status_code, 201)
        self.assertEqual(self.login("09123456789").status_code, 200)

    def test_ambiguous_phone_and_username_requires_email(self):
        self.assertEqual(self.register("09123456789").status_code, 201)
        self.assertEqual(self.register("Second").status_code, 201)
        with Session(self.engine) as db:
            user = db.scalar(select(UserModel).where(UserModel.username == "Second"))
            user.phone_number = "09123456789"
            db.commit()
        self.assertEqual(self.login("09123456789").status_code, 400)
        self.assertEqual(self.login("second@example.com").status_code, 200)

    def test_phone_only_identifier_still_works(self):
        self.register()
        with Session(self.engine) as db:
            db.scalar(select(UserModel)).phone_number = "09123456789"
            db.commit()
        self.assertEqual(self.login("09123456789").status_code, 200)


if __name__ == "__main__":
    unittest.main()
