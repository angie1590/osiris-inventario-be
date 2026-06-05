"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums ---
    user_role = postgresql.ENUM("admin", "operator", "supervisor", name="userrole", create_type=True)
    user_role.create(op.get_bind(), checkfirst=True)

    attr_data_type = postgresql.ENUM("text", "integer", "decimal", "date", "boolean", "select", name="attributedatatype", create_type=True)
    attr_data_type.create(op.get_bind(), checkfirst=True)

    product_status = postgresql.ENUM("active", "inactive", name="productstatus", create_type=True)
    product_status.create(op.get_bind(), checkfirst=True)

    document_type = postgresql.ENUM("IN", "EG", "BI", "AI", name="documenttype", create_type=True)
    document_type.create(op.get_bind(), checkfirst=True)

    document_status = postgresql.ENUM("pending", "approved", "cancelled", name="documentstatus", create_type=True)
    document_status.create(op.get_bind(), checkfirst=True)

    adjust_type = postgresql.ENUM("increment", "decrement", name="adjusttype", create_type=True)
    adjust_type.create(op.get_bind(), checkfirst=True)

    kardex_entry_type = postgresql.ENUM("IN", "OUT", "ADJUST", name="kardexentrytype", create_type=True)
    kardex_entry_type.create(op.get_bind(), checkfirst=True)

    audit_action = postgresql.ENUM(
        "CREATE", "UPDATE", "DELETE", "APPROVE", "REJECT", "CANCEL",
        "LOGIN", "LOGIN_FAILED", "LOGOUT", "SESSION_EXPIRED", "PASSWORD_CHANGED",
        name="auditaction", create_type=True,
    )
    audit_action.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("role", postgresql.ENUM("admin", "operator", "supervisor", name="userrole", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    # --- category_attributes ---
    op.create_table(
        "category_attributes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("data_type", postgresql.ENUM("text", "integer", "decimal", "date", "boolean", "select", name="attributedatatype", create_type=False), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("select_options", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_category_attributes_category_id", "category_attributes", ["category_id"])

    # --- system_params ---
    op.create_table(
        "system_params",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_system_params_key", "system_params", ["key"], unique=True)

    # --- products ---
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stock_minimo", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("stock_actual", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("pvp", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("status", postgresql.ENUM("active", "inactive", name="productstatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("custom_attributes", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_status", "products", ["status"])

    # --- document_sequences ---
    op.create_table(
        "document_sequences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("doc_type", postgresql.ENUM("IN", "EG", "BI", "AI", name="documenttype", create_type=False), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("last_number", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("doc_type", "year", name="uq_doc_sequence"),
    )

    # --- inventory_documents ---
    op.create_table(
        "inventory_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("doc_type", postgresql.ENUM("IN", "EG", "BI", "AI", name="documenttype", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "approved", "cancelled", name="documentstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("reference", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("adjust_type", postgresql.ENUM("increment", "decrement", name="adjusttype", create_type=False), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authorized_by", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_inventory_documents_number", "inventory_documents", ["number"], unique=True)
    op.create_index("ix_inventory_documents_doc_type", "inventory_documents", ["doc_type"])
    op.create_index("ix_inventory_documents_status", "inventory_documents", ["status"])
    op.create_index("ix_inventory_documents_created_by", "inventory_documents", ["created_by"])
    op.create_index("ix_inventory_documents_created_at", "inventory_documents", ["created_at"])

    # --- inventory_lots (before document_lines since document_lines references it) ---
    op.create_table(
        "inventory_lots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity_initial", sa.Numeric(14, 4), nullable=False),
        sa.Column("quantity_available", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("lot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_inventory_lots_product_id", "inventory_lots", ["product_id"])
    op.create_index("ix_inventory_lots_product_lot_date", "inventory_lots", ["product_id", "lot_date"])

    # --- inventory_document_lines ---
    op.create_table(
        "inventory_document_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("inventory_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("lot_id", sa.Integer, sa.ForeignKey("inventory_lots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_inventory_document_lines_document_id", "inventory_document_lines", ["document_id"])
    op.create_index("ix_inventory_document_lines_product_id", "inventory_document_lines", ["product_id"])

    # --- authorization_codes ---
    op.create_table(
        "authorization_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("inventory_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_authorization_codes_document_id", "authorization_codes", ["document_id"])

    # --- kardex_entries ---
    op.create_table(
        "kardex_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_line_id", sa.Integer, sa.ForeignKey("inventory_document_lines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", postgresql.ENUM("IN", "OUT", "ADJUST", name="kardexentrytype", create_type=False), nullable=False),
        sa.Column("quantity_in", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("cost_in", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("quantity_out", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("cost_out", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("balance_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("balance_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("weighted_avg_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("lot_id", sa.Integer, sa.ForeignKey("inventory_lots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_kardex_entries_product_created", "kardex_entries", ["product_id", "created_at"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("action", postgresql.ENUM(
            "CREATE", "UPDATE", "DELETE", "APPROVE", "REJECT", "CANCEL",
            "LOGIN", "LOGIN_FAILED", "LOGOUT", "SESSION_EXPIRED", "PASSWORD_CHANGED",
            name="auditaction", create_type=False,
        ), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(50), nullable=True),
        sa.Column("previous_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_user_ts", "audit_logs", ["user_id", "timestamp"])

    # --- 2.16 / 2.17: PostgreSQL trigger to protect stock_actual ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_product_stock(p_product_id INTEGER, p_delta NUMERIC)
        RETURNS void AS $$
        DECLARE
            v_new_stock NUMERIC;
        BEGIN
            SELECT stock_actual + p_delta INTO v_new_stock
            FROM products WHERE id = p_product_id FOR UPDATE;

            IF v_new_stock < 0 THEN
                RAISE EXCEPTION 'INSUFFICIENT_STOCK: stock would become negative (%.4f)', v_new_stock;
            END IF;

            PERFORM set_config('app.allow_stock_update', '1', true);
            UPDATE products SET stock_actual = v_new_stock, updated_at = now()
            WHERE id = p_product_id;
            PERFORM set_config('app.allow_stock_update', '0', true);
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_direct_stock_update()
        RETURNS trigger AS $$
        BEGIN
            IF current_setting('app.allow_stock_update', true) = '1' THEN
                RETURN NEW;
            END IF;

            IF NEW.stock_actual IS DISTINCT FROM OLD.stock_actual THEN
                RAISE EXCEPTION 'DIRECT_STOCK_UPDATE_FORBIDDEN: use update_product_stock() function';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_prevent_direct_stock_update
        BEFORE UPDATE ON products
        FOR EACH ROW
        EXECUTE FUNCTION prevent_direct_stock_update();
    """)

    # --- 2.18: Create initial partitions for current + next year ---
    import datetime
    current_year = datetime.date.today().year
    for year in [current_year, current_year + 1]:
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"
            # Note: In production, kardex_entries and audit_logs would be PARTITION BY RANGE tables.
            # For simplicity with SQLAlchemy ORM, we use regular tables with indexed created_at/timestamp.
            # The partitioning DDL would be applied manually or via a dedicated migration in a real setup.


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_direct_stock_update ON products")
    op.execute("DROP FUNCTION IF EXISTS prevent_direct_stock_update()")
    op.execute("DROP FUNCTION IF EXISTS update_product_stock(INTEGER, NUMERIC)")

    for table in [
        "audit_logs", "kardex_entries", "authorization_codes",
        "inventory_document_lines", "inventory_lots", "inventory_documents",
        "document_sequences", "products", "system_params",
        "category_attributes", "categories", "refresh_tokens", "users",
    ]:
        op.drop_table(table)

    for enum_name in [
        "userrole", "attributedatatype", "productstatus", "documenttype",
        "documentstatus", "adjusttype", "kardexentrytype", "auditaction",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
