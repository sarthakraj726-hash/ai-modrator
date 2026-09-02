"""Role-Based Access Control (RBAC) definitions and permission checks."""

from enum import Enum

from pydantic import BaseModel


class Role(str, Enum):
    """User roles defining system-wide or channel-level access levels."""

    DEVELOPER = "DEVELOPER"
    CREATOR = "CREATOR"
    MODERATOR = "MODERATOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    # System Administration
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_HEALTH_VIEW = "system:health:view"
    KEY_POOL_MANAGE = "keypool:manage"

    # Creator Management
    CREATOR_CREATE = "creator:create"
    CREATOR_READ = "creator:read"
    CREATOR_UPDATE = "creator:update"
    CREATOR_DELETE = "creator:delete"

    # Stream Session Management
    STREAM_START = "stream:start"
    STREAM_STOP = "stream:stop"
    STREAM_READ = "stream:read"
    STREAM_RESTART = "stream:restart"

    # Moderation Operations
    MODERATION_EXECUTE = "moderation:execute"
    MODERATION_CONFIG = "moderation:config"
    MODERATION_AUDIT_VIEW = "moderation:audit:view"

    # Chat & Commands
    COMMAND_EXECUTE = "command:execute"
    COMMAND_CUSTOM_MANAGE = "command:manage"


# Role-to-Permission Mapping Matrix
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.DEVELOPER: set(Permission),  # All permissions
    Role.CREATOR: {
        Permission.SYSTEM_HEALTH_VIEW,
        Permission.CREATOR_READ,
        Permission.CREATOR_UPDATE,
        Permission.STREAM_START,
        Permission.STREAM_STOP,
        Permission.STREAM_READ,
        Permission.STREAM_RESTART,
        Permission.MODERATION_CONFIG,
        Permission.MODERATION_AUDIT_VIEW,
        Permission.COMMAND_EXECUTE,
        Permission.COMMAND_CUSTOM_MANAGE,
    },
    Role.MODERATOR: {
        Permission.STREAM_READ,
        Permission.MODERATION_EXECUTE,
        Permission.MODERATION_AUDIT_VIEW,
        Permission.COMMAND_EXECUTE,
    },
    Role.VIEWER: {
        Permission.COMMAND_EXECUTE,
    },
}


class UserContext(BaseModel):
    """Context object representing the authenticated identity."""

    user_id: str
    role: Role
    creator_id: str | None = None  # None for developers, set for channel-scoped creators/moderators

    def has_permission(self, permission: Permission) -> bool:
        """Check if user role grants specific permission."""
        allowed_permissions = ROLE_PERMISSIONS.get(self.role, set())
        return permission in allowed_permissions

    def can_manage_creator(self, target_creator_id: str) -> bool:
        """Check if user can manage the given creator."""
        if self.role == Role.DEVELOPER:
            return True
        if self.role == Role.CREATOR and self.creator_id == target_creator_id:
            return True
        return False
