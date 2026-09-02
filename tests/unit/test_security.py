"""Unit tests for security, token validation, and RBAC."""

import pytest
from fastapi import HTTPException

from app.core.rbac import Permission, Role, UserContext
from app.core.security import generate_secure_token, verify_admin_secret


def test_generate_secure_token():
    token = generate_secure_token(32)
    assert isinstance(token, str)
    assert len(token) == 64


def test_rbac_permissions():
    dev_user = UserContext(user_id="dev-1", role=Role.DEVELOPER)
    assert dev_user.has_permission(Permission.SYSTEM_ADMIN)
    assert dev_user.has_permission(Permission.CREATOR_CREATE)
    assert dev_user.can_manage_creator("any-creator-id")

    creator_user = UserContext(user_id="c-1", role=Role.CREATOR, creator_id="c-1")
    assert not creator_user.has_permission(Permission.SYSTEM_ADMIN)
    assert creator_user.has_permission(Permission.STREAM_START)
    assert creator_user.can_manage_creator("c-1")
    assert not creator_user.can_manage_creator("c-2")

    viewer = UserContext(user_id="v-1", role=Role.VIEWER)
    assert viewer.has_permission(Permission.COMMAND_EXECUTE)
    assert not viewer.has_permission(Permission.STREAM_START)


def test_verify_admin_secret_valid():
    user = verify_admin_secret(x_admin_secret="test-admin-secret-12345", credentials=None)
    assert user.role == Role.DEVELOPER


def test_verify_admin_secret_invalid():
    with pytest.raises(HTTPException) as exc_info:
        verify_admin_secret(x_admin_secret="wrong-secret", credentials=None)
    assert exc_info.value.status_code == 403


def test_verify_admin_secret_missing():
    with pytest.raises(HTTPException) as exc_info:
        verify_admin_secret(x_admin_secret=None, credentials=None)
    assert exc_info.value.status_code == 401
