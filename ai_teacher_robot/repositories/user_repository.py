from typing import Optional, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager
from services.crypto_service import crypto_service

class UserRepository:
    """
    Enterprise UserRepository with:
    - Salted PBKDF2 password hashing & seamless legacy SHA256 migration.
    - Field-level AES-256 PII data encryption.
    """
    def __init__(self) -> None:
        self.collection_name = "users"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def ensure_indexes(self) -> None:
        """Startup DB reliability check: Auto-creates unique index on username."""
        try:
            col = await self._get_collection()
            await col.create_index("username", unique=True)
            logger.info("Successfully validated unique MongoDB index on 'users.username'.")
        except Exception as e:
            logger.warning(f"Note on MongoDB user index validation: {e}")

    async def register_user(
        self,
        username: str,
        password: str,
        role: str = "student",
        class_level: int = 6,
        email: Optional[str] = None
    ) -> str:
        col = await self._get_collection()
        
        # Check if user already exists
        existing = await col.find_one({"username": username})
        if existing:
            raise ValueError(f"User '{username}' already exists.")
            
        user_doc = {
            "username": username,
            "password_hash": crypto_service.hash_password(password),
            "role": role,
            "class_level": int(class_level),
            "email": crypto_service.encrypt_pii(email) if email else None
        }
        
        res = await col.insert_one(user_doc)
        inserted_id = str(res.inserted_id)
        logger.info(f"Registered user '{username}' with PBKDF2 salted password, role '{role}', and class level {class_level}.")
        return inserted_id

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        user = await col.find_one({"username": username})
        if not user:
            return None

        stored_hash = user.get("password_hash", "")
        is_valid, needs_upgrade = crypto_service.verify_password(password, stored_hash)

        if not is_valid:
            return None

        # Seamless Legacy SHA256 Migration Upgrade
        if needs_upgrade:
            new_pbkdf2_hash = crypto_service.hash_password(password)
            await col.update_one(
                {"_id": user["_id"]},
                {"$set": {"password_hash": new_pbkdf2_hash}}
            )
            logger.info(f"Seamlessly upgraded user '{username}' password hash from SHA256 to salted PBKDF2.")

        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "role": user.get("role", "student"),
            "class_level": user.get("class_level", 6),
            "email": crypto_service.decrypt_pii(user.get("email"))
        }

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        user = await col.find_one({"username": username})
        if user:
            return {
                "id": str(user["_id"]),
                "username": user["username"],
                "role": user.get("role", "student"),
                "class_level": user.get("class_level", 6),
                "email": crypto_service.decrypt_pii(user.get("email"))
            }
        return None

user_repository = UserRepository()
