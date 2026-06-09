from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, categories, products, inventory, kardex, reports, audit, admin, company, catalogs, remap

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/admin/users", tags=["admin"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(catalogs.router, prefix="/catalogs", tags=["catalogs"])
api_router.include_router(remap.router, prefix="/attribute-remap", tags=["remap"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(kardex.router, prefix="/kardex", tags=["kardex"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(company.router, prefix="/company", tags=["company"])
