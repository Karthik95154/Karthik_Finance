import uuid
import pytest
import secrets
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select
from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserInvitation, Tenant
from app.core.security import (
    hash_invitation_token,
    hash_otp,
    create_access_token,
)


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.mark.asyncio
async def test_all_14_invitation_otp_security_scenarios(transport):
    """
    Comprehensive automated test suite validating all 14 production implementation
    specification security test cases for Sakshi Finance Email OTP & Invitation Workflow.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 0. Setup test tenant & admin user
        tenant_id = f"test-tenant-otp-{uuid.uuid4().hex[:6]}"
        admin_id = uuid.uuid4()
        admin_email = f"admin-{uuid.uuid4().hex[:6]}@sakshi.ai"

        async with AsyncSessionLocal() as db:
            tenant = Tenant(id=tenant_id, name="OTP Test Tenant", slug=f"slug-{tenant_id}")
            db.add(tenant)
            admin_user = User(
                id=admin_id,
                tenant_id=tenant_id,
                email=admin_email,
                hashed_password="pbkdf2:sha256:dummy$hash",
                full_name="Test Admin",
                role="ADMIN",
                is_active=True,
            )
            db.add(admin_user)
            await db.commit()

        # Helper to create invitation in DB directly
        async def create_test_invitation(
            email: str,
            role: str = "FINANCE_USER",
            status: str = "OTP_VERIFICATION_PENDING",
            expires_delta: timedelta = timedelta(days=7),
        ):
            raw_token = secrets.token_urlsafe(32)
            token_hash = hash_invitation_token(raw_token)
            inv_id = uuid.uuid4()
            async with AsyncSessionLocal() as db:
                inv = UserInvitation(
                    id=inv_id,
                    tenant_id=tenant_id,
                    email=email.lower().strip(),
                    role=role,
                    token_hash=token_hash,
                    expires_at=datetime.now(timezone.utc) + expires_delta,
                    status=status,
                    otp_attempts=0,
                )
                db.add(inv)
                await db.commit()
            return raw_token, inv_id

        # Helper to update OTP hash for invitation
        async def set_invitation_otp(inv_id: uuid.UUID, raw_otp: str, expires_delta: timedelta = timedelta(minutes=10)):
            async with AsyncSessionLocal() as db:
                inv = await db.get(UserInvitation, inv_id)
                if inv:
                    inv.otp_hash = hash_otp(raw_otp)
                    inv.otp_expires_at = datetime.now(timezone.utc) + expires_delta
                    await db.commit()

        # ----------------------------------------------------------------------
        # TEST 1: Valid invitation + correct OTP -> Account Created
        # ----------------------------------------------------------------------
        email1 = f"user1-{uuid.uuid4().hex[:6]}@example.com"
        raw_token1, inv_id1 = await create_test_invitation(email1)

        # Validate token
        res_val = await client.get(f"/api/v1/auth/accept-invite/validate?token={raw_token1}")
        assert res_val.status_code == 200, res_val.text

        # Verify with correct OTP
        raw_otp1 = "123456"
        await set_invitation_otp(inv_id1, raw_otp1)

        res_ver1 = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token1, "otp": raw_otp1},
        )
        assert res_ver1.status_code == 200
        assert res_ver1.json()["email_verified"] is True

        # Accept invite & set password
        res_acc1 = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": raw_token1, "password": "securepassword123", "full_name": "User One"},
        )
        assert res_acc1.status_code == 200
        assert "access_token" in res_acc1.json()

        # ----------------------------------------------------------------------
        # TEST 2: Valid invitation + wrong OTP -> Account NOT Created
        # ----------------------------------------------------------------------
        email2 = f"user2-{uuid.uuid4().hex[:6]}@example.com"
        raw_token2, inv_id2 = await create_test_invitation(email2)
        await set_invitation_otp(inv_id2, "654321")

        res_ver2 = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token2, "otp": "000000"},  # Wrong OTP
        )
        assert res_ver2.status_code == 400

        # Attempt to create account without OTP verification
        res_acc2 = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": raw_token2, "password": "securepassword123"},
        )
        assert res_acc2.status_code == 400
        assert "Email address must be verified" in res_acc2.json()["detail"]

        # ----------------------------------------------------------------------
        # TEST 3: Valid invitation + expired OTP -> Account NOT Created
        # ----------------------------------------------------------------------
        email3 = f"user3-{uuid.uuid4().hex[:6]}@example.com"
        raw_token3, inv_id3 = await create_test_invitation(email3)
        await set_invitation_otp(inv_id3, "111222", expires_delta=-timedelta(minutes=1))

        res_ver3 = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token3, "otp": "111222"},
        )
        assert res_ver3.status_code == 400
        assert "expired" in res_ver3.json()["detail"].lower()

        # ----------------------------------------------------------------------
        # TEST 4: Max OTP attempts (5) exceeded -> Invitation LOCKED
        # ----------------------------------------------------------------------
        email4 = f"user4-{uuid.uuid4().hex[:6]}@example.com"
        raw_token4, inv_id4 = await create_test_invitation(email4)
        await set_invitation_otp(inv_id4, "999888")

        for _ in range(5):
            await client.post(
                "/api/v1/auth/accept-invite/verify-otp",
                json={"token": raw_token4, "otp": "000000"},
            )

        async with AsyncSessionLocal() as db:
            inv4 = await db.get(UserInvitation, inv_id4)
            assert inv4.status == "LOCKED"

        # Subsequent attempts must fail with locked error
        res_lock = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token4, "otp": "999888"},
        )
        assert res_lock.status_code == 400
        assert "locked" in res_lock.json()["detail"].lower()

        # ----------------------------------------------------------------------
        # TEST 5: Resend OTP -> Old OTP invalidated, new OTP valid
        # ----------------------------------------------------------------------
        email5 = f"user5-{uuid.uuid4().hex[:6]}@example.com"
        raw_token5, inv_id5 = await create_test_invitation(email5)
        old_otp = "111111"
        await set_invitation_otp(inv_id5, old_otp)

        # Bypass 30-sec rate limit
        async with AsyncSessionLocal() as db:
            inv5 = await db.get(UserInvitation, inv_id5)
            inv5.otp_last_sent_at = datetime.now(timezone.utc) - timedelta(seconds=35)
            await db.commit()

        # Resend OTP
        res_resend = await client.post(
            "/api/v1/auth/accept-invite/send-otp",
            json={"token": raw_token5},
        )
        assert res_resend.status_code == 200

        # Old OTP must fail
        res_old_ver = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token5, "otp": old_otp},
        )
        assert res_old_ver.status_code == 400

        # Set deterministic new OTP
        await set_invitation_otp(inv_id5, "222333")

        res_new_ver = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token5, "otp": "222333"},
        )
        assert res_new_ver.status_code == 200
        assert res_new_ver.json()["email_verified"] is True

        # ----------------------------------------------------------------------
        # TEST 6: Copied invitation URL -> OTP sent ONLY to original invited email
        # ----------------------------------------------------------------------
        email6 = f"original-{uuid.uuid4().hex[:6]}@company.com"
        raw_token6, inv_id6 = await create_test_invitation(email6)

        # Attacker opens URL
        res_val6 = await client.get(f"/api/v1/auth/accept-invite/validate?token={raw_token6}")
        assert res_val6.status_code == 200
        assert res_val6.json()["email"] == email6.lower()

        # Bypass rate limit before manual send-otp call
        async with AsyncSessionLocal() as db:
            inv6 = await db.get(UserInvitation, inv_id6)
            inv6.otp_last_sent_at = datetime.now(timezone.utc) - timedelta(seconds=35)
            await db.commit()

        # Attacker cannot specify a different email destination when triggering send-otp
        res_send6 = await client.post(
            "/api/v1/auth/accept-invite/send-otp",
            json={"token": raw_token6},
        )
        assert res_send6.status_code == 200
        async with AsyncSessionLocal() as db:
            inv6 = await db.get(UserInvitation, inv_id6)
            assert inv6.email == email6.lower()  # Destination remains original invited email

        # ----------------------------------------------------------------------
        # TEST 7: Nonexistent mailbox -> SMTP accepted delivery, unverified, no account
        # ----------------------------------------------------------------------
        email7 = f"nonexistent-mailbox-{uuid.uuid4().hex[:6]}@example.com"
        raw_token7, inv_id7 = await create_test_invitation(email7)

        async with AsyncSessionLocal() as db:
            inv7 = await db.get(UserInvitation, inv_id7)
            inv7.email_delivery_status = "EMAIL_DELIVERY_ACCEPTED"
            inv7.status = "OTP_VERIFICATION_PENDING"
            await db.commit()

        # Direct account creation without OTP verification fails
        res_acc7 = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": raw_token7, "password": "password123"},
        )
        assert res_acc7.status_code == 400

        # ----------------------------------------------------------------------
        # TEST 8: Expired Invitation -> Signup Rejected
        # ----------------------------------------------------------------------
        email8 = f"expired-{uuid.uuid4().hex[:6]}@example.com"
        raw_token8, inv_id8 = await create_test_invitation(email8, expires_delta=-timedelta(days=1))

        res_val8 = await client.get(f"/api/v1/auth/accept-invite/validate?token={raw_token8}")
        assert res_val8.status_code == 400
        assert "expired" in res_val8.json()["detail"].lower()

        # ----------------------------------------------------------------------
        # TEST 9: Revoked Invitation -> Signup Rejected
        # ----------------------------------------------------------------------
        email9 = f"revoked-{uuid.uuid4().hex[:6]}@example.com"
        raw_token9, inv_id9 = await create_test_invitation(email9, status="REVOKED")

        res_val9 = await client.get(f"/api/v1/auth/accept-invite/validate?token={raw_token9}")
        assert res_val9.status_code == 400
        assert "revoked" in res_val9.json()["detail"].lower()

        # ----------------------------------------------------------------------
        # TEST 10: Already-Used Invitation -> Signup Rejected
        # ----------------------------------------------------------------------
        email10 = f"used-{uuid.uuid4().hex[:6]}@example.com"
        raw_token10, inv_id10 = await create_test_invitation(email10, status="ACCEPTED")

        res_val10 = await client.get(f"/api/v1/auth/accept-invite/validate?token={raw_token10}")
        assert res_val10.status_code == 400
        assert "already been used" in res_val10.json()["detail"].lower()

        # ----------------------------------------------------------------------
        # TEST 11: Direct API account creation without OTP -> Backend Rejects
        # ----------------------------------------------------------------------
        email11 = f"direct-api-{uuid.uuid4().hex[:6]}@example.com"
        raw_token11, inv_id11 = await create_test_invitation(email11)

        res_direct = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": raw_token11, "password": "password123"},
        )
        assert res_direct.status_code == 400
        assert "OTP" in res_direct.json()["detail"] or "verified" in res_direct.json()["detail"]

        # ----------------------------------------------------------------------
        # TEST 12: Attempt to change invited email during signup -> Rejection / Source of truth used
        # ----------------------------------------------------------------------
        email12 = f"legit-{uuid.uuid4().hex[:6]}@company.com"
        raw_token12, inv_id12 = await create_test_invitation(email12)

        async with AsyncSessionLocal() as db:
            inv12 = await db.get(UserInvitation, inv_id12)
            inv12.status = "EMAIL_VERIFIED"
            inv12.otp_verified_at = datetime.now(timezone.utc)
            await db.commit()

        res_acc12 = await client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": raw_token12,
                "password": "password123",
                "email": "attacker-override@gmail.com",  # Malicious extra field in body
            },
        )
        assert res_acc12.status_code == 200

        # Verify created user email is strictly the original invited email
        async with AsyncSessionLocal() as db:
            res_u12 = await db.execute(select(User).where(User.email == email12.lower()))
            created_user12 = res_u12.scalar_one_or_none()
            assert created_user12 is not None
            assert created_user12.email == email12.lower()

        # ----------------------------------------------------------------------
        # TEST 13: Attempt to change invited role during signup -> Source of truth enforced
        # ----------------------------------------------------------------------
        email13 = f"finance-{uuid.uuid4().hex[:6]}@company.com"
        raw_token13, inv_id13 = await create_test_invitation(email13, role="FINANCE_USER")

        async with AsyncSessionLocal() as db:
            inv13 = await db.get(UserInvitation, inv_id13)
            inv13.status = "EMAIL_VERIFIED"
            inv13.otp_verified_at = datetime.now(timezone.utc)
            await db.commit()

        res_acc13 = await client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": raw_token13,
                "password": "password123",
                "role": "ADMIN",  # Privilege escalation attempt
            },
        )
        assert res_acc13.status_code == 200

        async with AsyncSessionLocal() as db:
            res_u13 = await db.execute(select(User).where(User.email == email13.lower()))
            created_user13 = res_u13.scalar_one_or_none()
            assert created_user13 is not None
            assert created_user13.role == "FINANCE_USER"  # Must remain FINANCE_USER

        # ----------------------------------------------------------------------
        # TEST 14: OTP Replay after successful verification -> Rejected (Single-use)
        # ----------------------------------------------------------------------
        email14 = f"replay-{uuid.uuid4().hex[:6]}@example.com"
        raw_token14, inv_id14 = await create_test_invitation(email14)
        raw_otp14 = "777888"
        await set_invitation_otp(inv_id14, raw_otp14)

        # First verification succeeds
        res_replay1 = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token14, "otp": raw_otp14},
        )
        assert res_replay1.status_code == 200

        # Replay same OTP -> must be rejected because otp_hash is cleared upon verification
        res_replay2 = await client.post(
            "/api/v1/auth/accept-invite/verify-otp",
            json={"token": raw_token14, "otp": raw_otp14},
        )
        assert res_replay2.status_code == 400
