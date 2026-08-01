"""Migra catalogos y saldo inicial desde un dump MySQL legado.

Uso:
    python -m scripts.migrate_legacy_dump Dump20260730.sql
    python -m scripts.migrate_legacy_dump Dump20260730.sql --apply --actor admin
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


INITIAL_COST_RATE = Decimal("0.65")


@dataclass(frozen=True)
class MigrationPlan:
    tables: dict[str, list[list[Any]]]
    duplicate_barcodes: set[str]
    excluded_product_ids: set[int]
    invalid_supplier_ids: set[int]
    products: list[list[Any]]
    suppliers: list[list[Any]]
    initial_stock: list[list[Any]]
    product_attributes: dict[int, dict[str, str]]
    invalid_attribute_rows: list[list[Any]]
    empty_attribute_rows: list[list[Any]]
    conflicting_attributes: dict[int, dict[str, list[str]]]
    reactivated_category_ids: set[int]
    flattened_category_parents: dict[int, int]


def _parse_tuple(blob: bytes) -> list[Any]:
    tokens: list[bytes] = []
    current = bytearray()
    quoted = escaped = False
    for char in blob[1:-1]:
        if quoted:
            current.append(char)
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 39:
                quoted = False
        elif char == 39:
            quoted = True
            current.append(char)
        elif char == 44:
            tokens.append(bytes(current))
            current.clear()
        else:
            current.append(char)
    tokens.append(bytes(current))

    escapes = {48: 0, 39: 39, 34: 34, 98: 8, 110: 10, 114: 13, 116: 9, 90: 26, 92: 92}
    values: list[Any] = []
    for token in tokens:
        if token == b"NULL":
            values.append(None)
        elif token.startswith(b"'") and token.endswith(b"'"):
            source = token[1:-1]
            decoded = bytearray()
            index = 0
            while index < len(source):
                if source[index] == 92 and index + 1 < len(source):
                    index += 1
                    decoded.append(escapes.get(source[index], source[index]))
                else:
                    decoded.append(source[index])
                index += 1
            values.append(decoded.decode("utf-8"))
        else:
            text = token.decode("ascii")
            values.append(Decimal(text) if any(char in text.lower() for char in (".", "e")) else int(text))
    return values


def _extract_rows(raw: bytes, table: str) -> list[list[Any]]:
    marker = f"INSERT INTO `{table}` VALUES ".encode()
    rows: list[list[Any]] = []
    offset = 0
    while (start := raw.find(marker, offset)) >= 0:
        start += len(marker)
        lf_end = raw.find(b";\n", start)
        crlf_end = raw.find(b";\r\n", start)
        candidates = [end for end in (lf_end, crlf_end) if end >= 0]
        if not candidates:
            raise ValueError(f"INSERT incompleto para la tabla {table}")
        end = min(candidates)
        data = raw[start:end]
        offset = end + (3 if raw[end:end + 3] == b";\r\n" else 2)
        index = 0
        while index < len(data):
            if data[index] != 40:
                index += 1
                continue
            row_start = index
            depth = 0
            quoted = escaped = False
            while index < len(data):
                char = data[index]
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == 92:
                        escaped = True
                    elif char == 39:
                        quoted = False
                elif char == 39:
                    quoted = True
                elif char == 40:
                    depth += 1
                elif char == 41:
                    depth -= 1
                    if depth == 0:
                        rows.append(_parse_tuple(data[row_start:index + 1]))
                        index += 1
                        break
                index += 1
    return rows


def _valid_ecuador_ruc(value: str) -> bool:
    if len(value) != 13 or not value.isdigit() or not 1 <= int(value[:2]) <= 24:
        return False
    third = int(value[2])
    if third < 6:
        total = 0
        for index, coefficient in enumerate((2, 1, 2, 1, 2, 1, 2, 1, 2)):
            product = int(value[index]) * coefficient
            total += product - 9 if product >= 10 else product
        return (10 - total % 10) % 10 == int(value[9]) and value[10:] != "000"
    if third == 6:
        total = sum(int(value[index]) * coefficient for index, coefficient in enumerate((3, 2, 7, 6, 5, 4, 3, 2)))
        check = 11 - total % 11
        check = 0 if check == 11 else check
        return check != 10 and check == int(value[8]) and value[9:] != "0000"
    if third == 9:
        total = sum(int(value[index]) * coefficient for index, coefficient in enumerate((4, 3, 2, 7, 6, 5, 4, 3, 2)))
        check = 11 - total % 11
        check = 0 if check == 11 else check
        return check != 10 and check == int(value[9]) and value[10:] != "000"
    return False


def initial_unit_cost(pvp: Any) -> Decimal:
    return (Decimal(str(pvp or 0)) * INITIAL_COST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_plan(path: Path) -> MigrationPlan:
    raw = path.read_bytes()
    names = ("categoria", "tipo_de_producto", "atributo", "atributo_descripcion", "proveedor", "producto")
    tables = {name: _extract_rows(raw, name) for name in names}

    barcode_counts = Counter(str(row[2]).strip().casefold() for row in tables["producto"])
    duplicate_barcodes = {barcode for barcode, count in barcode_counts.items() if count > 1}
    excluded_product_ids = {
        row[0]
        for row in tables["producto"]
        if str(row[2]).strip().casefold() in duplicate_barcodes
    }
    products = [row for row in tables["producto"] if row[0] not in excluded_product_ids]

    invalid_supplier_ids = {
        row[0] for row in tables["proveedor"] if not _valid_ecuador_ruc(str(row[1]).strip())
    }
    suppliers_by_ruc: dict[str, list[list[Any]]] = defaultdict(list)
    for row in tables["proveedor"]:
        ruc = str(row[1]).strip()
        if row[0] not in invalid_supplier_ids:
            suppliers_by_ruc[ruc].append(row)
    suppliers = [
        sorted(rows, key=lambda row: (row[9] != "\x01", row[0]))[0]
        for rows in suppliers_by_ruc.values()
    ]

    attribute_names = {
        row[0]: str(row[1]).strip().upper()
        for row in tables["atributo"]
        if row[1] is not None and str(row[1]).strip()
    }
    type_names = {
        row[0]: str(row[1]).strip().upper()
        for row in tables["tipo_de_producto"]
    }
    invalid_attribute_rows = [
        row for row in tables["atributo_descripcion"] if row[3] not in attribute_names
    ]
    empty_attribute_rows = [
        row
        for row in tables["atributo_descripcion"]
        if row[1] is None or not str(row[1]).strip()
    ]
    values_by_product: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in tables["atributo_descripcion"]:
        if row[4] in excluded_product_ids or row[3] not in attribute_names:
            continue
        value = str(row[1]).strip() if row[1] is not None else ""
        if value:
            values_by_product[row[4]][attribute_names[row[3]]].append(value.upper())

    product_attributes: dict[int, dict[str, str]] = {}
    conflicting_attributes: dict[int, dict[str, list[str]]] = {}
    for product in products:
        product_id = product[0]
        values = values_by_product[product_id]
        mapped = {"TIPO DE PRODUCTO": type_names[product[16]]}
        for name, raw_values in values.items():
            unique_values = list(dict.fromkeys(raw_values))
            if len(unique_values) == 1:
                mapped[name] = unique_values[0]
            else:
                conflicting_attributes.setdefault(product_id, {})[name] = unique_values
        product_attributes[product_id] = mapped

    initial_stock = [row for row in products if Decimal(str(row[13] or 0)) > 0]
    categories_by_id = {row[0]: row for row in tables["categoria"]}
    flattened_category_parents = {
        row[0]: row[3]
        for row in tables["categoria"]
        if row[3] is not None
        and str(row[1]).strip().upper() == "MOCASIN"
        and str(categories_by_id[row[3]][1]).strip().upper() == "ZAPATO"
    }
    category_parents = {row[0]: row[3] for row in tables["categoria"]}
    required_active_categories = {
        row[15] for row in products if row[12] == "\x01"
    }
    for category_id in tuple(required_active_categories):
        parent_id = category_parents[category_id]
        while parent_id is not None:
            required_active_categories.add(parent_id)
            parent_id = category_parents[parent_id]
    reactivated_category_ids = {
        row[0]
        for row in tables["categoria"]
        if row[2] != "\x01" and row[0] in required_active_categories
    }
    return MigrationPlan(
        tables=tables,
        duplicate_barcodes=duplicate_barcodes,
        excluded_product_ids=excluded_product_ids,
        invalid_supplier_ids=invalid_supplier_ids,
        products=products,
        suppliers=suppliers,
        initial_stock=initial_stock,
        product_attributes=product_attributes,
        invalid_attribute_rows=invalid_attribute_rows,
        empty_attribute_rows=empty_attribute_rows,
        conflicting_attributes=conflicting_attributes,
        reactivated_category_ids=reactivated_category_ids,
        flattened_category_parents=flattened_category_parents,
    )


def print_summary(plan: MigrationPlan) -> None:
    stock_units = sum(Decimal(str(row[13])) for row in plan.initial_stock)
    stock_value = sum(Decimal(str(row[13])) * initial_unit_cost(row[10]) for row in plan.initial_stock)
    print(f"Categorias: {len(plan.tables['categoria'])}")
    print(f"Productos origen: {len(plan.tables['producto'])}")
    print(f"Codigos duplicados: {len(plan.duplicate_barcodes)}")
    print(f"Productos excluidos por codigo duplicado: {len(plan.excluded_product_ids)}")
    print(f"Productos a migrar: {len(plan.products)}")
    print(f"Proveedores excluidos por RUC invalido: {len(plan.invalid_supplier_ids)}")
    print(f"Proveedores validos y unicos a migrar: {len(plan.suppliers)}")
    print(f"Valores de atributo sin atributo: {len(plan.invalid_attribute_rows)}")
    print(f"Valores de atributo vacios: {len(plan.empty_attribute_rows)}")
    print(f"Productos con atributos conflictivos: {len(plan.conflicting_attributes)}")
    print(f"Categorias reactivadas por productos activos: {len(plan.reactivated_category_ids)}")
    print(f"Categorias aplanadas en su padre: {len(plan.flattened_category_parents)}")
    print(f"Lineas de saldo inicial: {len(plan.initial_stock)}")
    print(f"Unidades de saldo inicial: {stock_units}")
    print(f"Valor de saldo inicial al 65% del PVP: {stock_value.quantize(Decimal('0.01'))}")


def _phone(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if 7 <= len(digits) <= 15 else None


def _date(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value else None


def _report(plan: MigrationPlan) -> dict[str, Any]:
    products_by_id = {row[0]: row for row in plan.tables["producto"]}
    suppliers_by_id = {row[0]: row for row in plan.tables["proveedor"]}
    return {
        "summary": {
            "source_products": len(plan.tables["producto"]),
            "migrated_products": len(plan.products),
            "duplicate_barcode_groups": len(plan.duplicate_barcodes),
            "excluded_duplicate_products": len(plan.excluded_product_ids),
            "excluded_invalid_suppliers": len(plan.invalid_supplier_ids),
            "migrated_suppliers": len(plan.suppliers),
            "initial_stock_lines": len(plan.initial_stock),
            "reactivated_categories": len(plan.reactivated_category_ids),
            "flattened_categories": len(plan.flattened_category_parents),
        },
        "excluded_products": [
            {"id": product_id, "name": products_by_id[product_id][1], "barcode": products_by_id[product_id][2]}
            for product_id in sorted(plan.excluded_product_ids)
        ],
        "excluded_suppliers": [
            {"id": supplier_id, "ruc": suppliers_by_id[supplier_id][1], "trade_name": suppliers_by_id[supplier_id][6]}
            for supplier_id in sorted(plan.invalid_supplier_ids)
        ],
        "attribute_anomalies": {
            "missing_attribute_rows": len(plan.invalid_attribute_rows),
            "empty_value_rows": len(plan.empty_attribute_rows),
            "conflicts": plan.conflicting_attributes,
        },
        "reactivated_category_ids": sorted(plan.reactivated_category_ids),
        "flattened_category_parents": plan.flattened_category_parents,
        "negative_stock_normalized": [
            {"id": row[0], "name": row[1], "barcode": row[2], "source_stock": str(row[13])}
            for row in plan.products
            if Decimal(str(row[13] or 0)) < 0
        ],
        "rules": {
            "duplicate_barcodes": "exclude_all_products_in_group",
            "invalid_ruc": "exclude_supplier",
            "product_supplier_relation": "ignored",
            "negative_stock": "zero",
            "initial_unit_cost": "pvp * 0.65, rounded to 2 decimals",
        },
    }


async def apply_plan(plan: MigrationPlan, actor: str, session_factory: Any = None) -> None:
    from sqlalchemy import func, select

    from app.core.database import AsyncSessionLocal
    from app.models.catalog import Catalog, CatalogValue
    from app.models.category import Category, CategoryAttribute
    from app.models.enums import AttributeDataType, AuditAction, DocumentStatus, DocumentType, ProductStatus
    from app.models.inventory import InventoryDocument, InventoryDocumentLine, InventorySupplier
    from app.models.product import Product
    from app.models.user import User
    from app.repositories.inventory_repository import InventoryRepository
    from app.repositories.product_repository import ProductRepository
    from app.services.audit_service import AuditService
    from app.services.kardex_service import KardexService

    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        try:
            user = (await session.execute(select(User).where(User.username == actor, User.is_active.is_(True)))).scalar_one_or_none()
            if user is None:
                raise ValueError(f"Usuario activo no encontrado: {actor}")

            for model in (Category, Product, InventorySupplier, Catalog, InventoryDocument):
                count = await session.scalar(select(func.count()).select_from(model))
                if count:
                    raise ValueError(f"La tabla {model.__tablename__} debe estar vacia")

            category_map: dict[int, Category] = {}
            source_categories = plan.tables["categoria"]
            for row in source_categories:
                if row[3] is None:
                    category = Category(
                        name=str(row[1]).strip(),
                        is_active=row[2] == "\x01" or row[0] in plan.reactivated_category_ids,
                    )
                    session.add(category)
                    category_map[row[0]] = category
            await session.flush()
            for row in source_categories:
                if row[3] is not None and row[0] not in plan.flattened_category_parents:
                    category = Category(
                        name=str(row[1]).strip(),
                        parent_id=category_map[row[3]].id,
                        is_active=row[2] == "\x01" or row[0] in plan.reactivated_category_ids,
                    )
                    session.add(category)
                    category_map[row[0]] = category
            await session.flush()

            source_parent_ids = {
                row[3]
                for row in source_categories
                if row[3] is not None and row[0] not in plan.flattened_category_parents
            }
            product_category_map = {category_id: category for category_id, category in category_map.items()}
            for category_id, parent_id in plan.flattened_category_parents.items():
                product_category_map[category_id] = category_map[parent_id]
            for source_parent_id in source_parent_ids:
                if any(product[15] == source_parent_id for product in plan.products):
                    default = Category(
                        name="Sin clasificar",
                        parent_id=category_map[source_parent_id].id,
                        is_default=True,
                    )
                    session.add(default)
                    await session.flush()
                    product_category_map[source_parent_id] = default

            values_by_name: dict[str, set[str]] = defaultdict(set)
            category_attribute_names: dict[int, set[str]] = defaultdict(set)
            for source_product in plan.products:
                target_category = product_category_map[source_product[15]]
                for name, value in plan.product_attributes[source_product[0]].items():
                    values_by_name[name].add(value)
                    category_attribute_names[target_category.id].add(name)

            catalog_ids: dict[str, int] = {}
            catalog_names = {
                "TIPO DE PRODUCTO": "Tipos de producto",
                "TALLA": "Tallas",
                "MARCA": "Marcas",
                "COLOR": "Colores",
            }
            for attribute_name, values in values_by_name.items():
                catalog = Catalog(name=catalog_names.get(attribute_name, attribute_name.title()))
                session.add(catalog)
                await session.flush()
                catalog_ids[attribute_name] = catalog.id
                session.add_all(
                    CatalogValue(catalog_id=catalog.id, value=value)
                    for value in sorted(values, key=str.casefold)
                )
            await session.flush()

            for category_id, names in category_attribute_names.items():
                session.add_all(
                    CategoryAttribute(
                        category_id=category_id,
                        name=name,
                        data_type=AttributeDataType.catalog,
                        catalog_id=catalog_ids[name],
                    )
                    for name in sorted(names)
                )

            product_map: dict[int, Product] = {}
            for row in plan.products:
                product = Product(
                    isbn=str(row[2]).strip(),
                    codigo_interno=str(row[9]).strip() if row[9] is not None and str(row[9]).strip() else None,
                    name=str(row[1]).strip(),
                    category_id=product_category_map[row[15]].id,
                    stock_minimo=Decimal("0"),
                    stock_actual=Decimal("0"),
                    pvp=Decimal(str(row[10] or 0)),
                    status=ProductStatus.active if row[12] == "\x01" else ProductStatus.inactive,
                    custom_attributes=plan.product_attributes[row[0]],
                    created_at=_date(row[6]),
                    updated_at=_date(row[7]) or _date(row[6]),
                )
                session.add(product)
                product_map[row[0]] = product
            await session.flush()

            for row in plan.suppliers:
                session.add(
                    InventorySupplier(
                        identification_type="ruc",
                        ruc=str(row[1]).strip(),
                        trade_name=str(row[6]).strip().upper(),
                        legal_name=str(row[7]).strip().upper(),
                        address=str(row[2]).strip().upper() if row[2] else None,
                        phone=_phone(row[3]),
                        is_active=row[9] == "\x01",
                    )
                )
            await session.flush()

            inventory_repo = InventoryRepository(session)
            product_repo = ProductRepository(session)
            number = await inventory_repo.generate_document_number(DocumentType.IN, datetime.now(timezone.utc).year)
            document = InventoryDocument(
                number=number,
                doc_type=DocumentType.IN,
                status=DocumentStatus.approved,
                ingreso_type="initial_inventory",
                purchase_document_type="inventory_act",
                reference="Migracion de saldo inicial",
                notes="Saldo inicial migrado. Costo unitario calculado como el 65% del PVP.",
                created_by=user.id,
            )
            lines = [
                InventoryDocumentLine(
                    product_id=product_map[row[0]].id,
                    quantity=Decimal(str(row[13])),
                    unit_cost=initial_unit_cost(row[10]),
                    unit_price=Decimal(str(row[10] or 0)),
                )
                for row in plan.initial_stock
            ]
            document = await inventory_repo.create_document(document, lines)
            for line in document.lines:
                await product_repo.update_stock(line.product_id, line.quantity)
            await KardexService(session, await _kardex_method(session)).record_entry(document, document.lines)

            await AuditService(session).log(
                AuditAction.CREATE,
                user_id=user.id,
                username=user.username,
                entity_type="legacy_migration",
                entity_id=document.id,
                new=_report(plan)["summary"],
                description="Migracion desde dump MySQL con saldo inicial al 65% del PVP",
            )
            await session.commit()
            print(f"Migracion aplicada. Documento de saldo inicial: {document.number}")
        except Exception:
            await session.rollback()
            raise


async def _kardex_method(session: Any) -> str:
    from sqlalchemy import select

    from app.models.system_param import SystemParam

    param = (await session.execute(select(SystemParam).where(SystemParam.key == "kardex_method"))).scalar_one_or_none()
    return param.value if param else "PEPS"


async def flatten_existing_shoe_category(apply: bool = False, session_factory: Any = None) -> None:
    from sqlalchemy import delete, func, select, update

    from app.core.database import AsyncSessionLocal
    from app.models.category import Category, CategoryAttribute
    from app.models.product import Product

    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        shoe = await session.scalar(
            select(Category).where(
                func.upper(Category.name) == "ZAPATO", Category.parent_id.is_(None)
            )
        )
        if not shoe:
            raise ValueError("No se encontro la categoria raiz ZAPATO")

        children = list(
            (
                await session.scalars(
                    select(Category).where(
                        Category.parent_id == shoe.id,
                        func.upper(Category.name).in_(["MOCASIN", "SIN CLASIFICAR"]),
                    )
                )
            ).all()
        )
        child_ids = [category.id for category in children]
        product_count = 0
        if child_ids:
            product_count = await session.scalar(
                select(func.count()).select_from(Product).where(Product.category_id.in_(child_ids))
            )

        print(f"Categorias a eliminar: {', '.join(category.name for category in children) or 'ninguna'}")
        print(f"Productos a mover a ZAPATO: {product_count}")
        if not apply or not child_ids:
            print("Sin cambios." if not apply else "ZAPATO ya esta aplanada.")
            return

        existing_names = set(
            await session.scalars(
                select(CategoryAttribute.name).where(CategoryAttribute.category_id == shoe.id)
            )
        )
        child_attributes = list(
            (
                await session.scalars(
                    select(CategoryAttribute).where(CategoryAttribute.category_id.in_(child_ids))
                )
            ).all()
        )
        for attribute in child_attributes:
            if attribute.name not in existing_names:
                attribute.category_id = shoe.id
                existing_names.add(attribute.name)

        await session.execute(update(Product).where(Product.category_id.in_(child_ids)).values(category_id=shoe.id))
        await session.execute(delete(Category).where(Category.id.in_(child_ids)))
        await session.commit()
        print("ZAPATO aplanada correctamente.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra el dump MySQL legado a Osiris")
    parser.add_argument("dump", type=Path, nargs="?")
    parser.add_argument("--apply", action="store_true", help="Aplica el plan a la base configurada")
    parser.add_argument(
        "--flatten-shoe-existing",
        action="store_true",
        help="Aplana ZAPATO en una base ya migrada; usa --apply para confirmar",
    )
    parser.add_argument("--actor", default="admin", help="Usuario que registra la migracion")
    parser.add_argument("--report", type=Path, default=Path("migration-report.json"), help="Ruta del reporte detallado JSON")
    args = parser.parse_args()

    if args.flatten_shoe_existing:
        asyncio.run(flatten_existing_shoe_category(args.apply))
        return
    if args.dump is None:
        parser.error("dump es obligatorio salvo con --flatten-shoe-existing")

    plan = build_plan(args.dump)
    print_summary(plan)
    args.report.write_text(json.dumps(_report(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reporte escrito en {args.report}")
    if args.apply:
        asyncio.run(apply_plan(plan, args.actor))
    else:
        print("Dry-run completado. No se modifico la base de datos.")


if __name__ == "__main__":
    main()