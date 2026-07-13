USER_CREATE = "user.create"
USER_READ = "user.read"
USER_UPDATE = "user.update"
USER_DELETE = "user.delete"
USER_DEACTIVATE = "user.deactivate"

ROLE_ASSIGN = "role.assign"
ROLE_REMOVE = "role.remove"

ALL_PERMISSIONS = [
    USER_CREATE,
    USER_READ,
    USER_UPDATE,
    USER_DELETE,
    USER_DEACTIVATE,
    ROLE_ASSIGN,
    ROLE_REMOVE,
]

DEFAULT_ROLES: dict[str, list[str]] = {
    "admin": ALL_PERMISSIONS,
    "manager": [USER_CREATE, USER_READ, USER_UPDATE, USER_DEACTIVATE],
    "user": [USER_READ],
}
