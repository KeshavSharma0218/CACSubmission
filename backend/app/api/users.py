"""Reserved user router; authentication endpoints remain an intentional future feature."""

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])
