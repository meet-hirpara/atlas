"""Pluggable storage backends for Atlas (SQL, MongoDB, Redis)."""

from app.storage.manager import get_storage_manager, storage_manager

__all__ = ["get_storage_manager", "storage_manager"]
