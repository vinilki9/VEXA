
from fastapi import APIRouter

from app.platform_admin_auth import router as platform_admin_auth_router
from app.organization_api import router as platform_admin_organizations_router


router = APIRouter()

router.include_router(platform_admin_auth_router)
router.include_router(platform_admin_organizations_router)
