from fastapi import APIRouter

from app.api.endpoints import internal_douyin

router = APIRouter()
router.include_router(internal_douyin.router)
