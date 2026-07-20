import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    supervisor = "supervisor"


class AttributeDataType(str, enum.Enum):
    text = "text"
    integer = "integer"
    decimal = "decimal"
    date = "date"
    boolean = "boolean"
    select = "select"
    catalog = "catalog"


class ProductStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class DocumentType(str, enum.Enum):
    IN = "IN"
    EG = "EG"
    BI = "BI"
    AI = "AI"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    cancelled = "cancelled"  # a pending document that was cancelled
    voided = "voided"  # an approved document that was annulled (effect reversed)


class AdjustType(str, enum.Enum):
    increment = "increment"
    decrement = "decrement"


class IngresoType(str, enum.Enum):
    purchase = "purchase"
    initial_inventory = "initial_inventory"
    adjustment_positive = "adjustment_positive"
    customer_return = "customer_return"
    production = "production"
    transfer_received = "transfer_received"
    other = "other"


class KardexEntryType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CANCEL = "CANCEL"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
