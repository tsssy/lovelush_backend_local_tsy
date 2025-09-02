"""Base repository abstract class with common patterns."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from bson import ObjectId
from motor.core import AgnosticCollection

from app.core.logging import get_logger
from app.infrastructure.database.mongodb import mongodb

T = TypeVar("T")
CreateT = TypeVar("CreateT")
UpdateT = TypeVar("UpdateT")

logger = get_logger(__name__)


class BaseRepositoryInterface(ABC, Generic[T, CreateT, UpdateT]):
    """Base repository interface defining common operations."""

    @abstractmethod
    async def create(self, data: CreateT) -> T:
        """Create a new entity."""
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def update(self, entity_id: str, data: UpdateT) -> Optional[T]:
        """Update entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete entity."""
        pass

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination."""
        pass

    @abstractmethod
    async def count_all(self) -> int:
        """Count total entities."""
        pass


class BaseRepository(BaseRepositoryInterface[T, CreateT, UpdateT]):
    """Base MongoDB repository with common functionality."""

    def __init__(self, collection_name: str, model_class: type):
        """Initialize base repository.

        Args:
            collection_name: MongoDB collection name
            model_class: Pydantic model class
        """
        self.collection_name = collection_name
        self.model_class = model_class
        self._collection: Optional[AgnosticCollection] = None
        logger.debug(
            f"{self.__class__.__name__} initialized for collection: {collection_name}"
        )

    @property
    def collection(self) -> AgnosticCollection:
        """Get MongoDB collection."""
        if self._collection is None:
            db = mongodb.get_database()
            self._collection = db[self.collection_name]
        return self._collection

    def _convert_doc_ids_to_strings(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ObjectId fields to strings for model compatibility, except primary key."""
        if not doc:
            return doc

        # Convert the document by replacing ObjectId values with strings
        # BUT keep _id as ObjectId (primary key should remain as ObjectId)
        converted_doc = {}
        for key, value in doc.items():
            if key == "_id":
                # Keep primary key as ObjectId, but convert to string for Pydantic
                converted_doc[key] = (
                    str(value) if isinstance(value, ObjectId) else value
                )
            elif isinstance(value, ObjectId):
                # Convert foreign key ObjectIds to strings
                converted_doc[key] = str(value)
            elif isinstance(value, list):
                # Handle lists that might contain ObjectIds
                converted_doc[key] = [
                    str(item) if isinstance(item, ObjectId) else item for item in value
                ]
            elif isinstance(value, dict):
                # Recursively handle nested dictionaries
                converted_doc[key] = self._convert_doc_ids_to_strings(value)
            else:
                converted_doc[key] = value

        return converted_doc

    def _convert_to_object_id(self, entity_id: str) -> str:
        """Keep string ID as is - no conversion needed."""
        return entity_id

    def _add_timestamps(
        self, data: Dict[str, Any], is_update: bool = False
    ) -> Dict[str, Any]:
        """Add created_at and updated_at timestamps."""
        now = datetime.now(timezone.utc)
        if not is_update:
            data["created_at"] = now
        data["updated_at"] = now
        return data

    def _convert_to_dict(self, data: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        """Convert data to dictionary format."""
        if isinstance(data, dict):
            return data

        # Try Pydantic v2 method first
        if hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
            try:
                return data.model_dump(exclude_unset=True)
            except Exception:
                pass

        # Try Pydantic v1 method
        if hasattr(data, "dict") and callable(getattr(data, "dict")):
            try:
                return data.dict(exclude_unset=True)
            except Exception:
                pass

        # Fallback: return empty dict if conversion fails
        logger.warning(
            f"Unable to convert data to dict, returning empty dict: {type(data)}"
        )
        return {}

    async def create(self, data: CreateT) -> T:
        """Create a new entity."""
        try:
            entity_dict = self._convert_to_dict(data)
            entity_dict = self._add_timestamps(entity_dict)

            entity = self.model_class(**entity_dict)
            result = await self.collection.insert_one(
                entity.model_dump(by_alias=True, exclude={"id"})
            )

            # Create new entity with string ID
            entity_dict["_id"] = str(result.inserted_id)
            created_entity = self.model_class(**entity_dict)

            logger.info(
                f"Created {self.model_class.__name__} with ID: {created_entity.id}"
            )
            return created_entity
        except Exception as e:
            logger.error(f"Failed to create {self.model_class.__name__}: {e}")
            raise

    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        try:
            # Try ObjectId first for backwards compatibility
            try:
                obj_id = ObjectId(entity_id)
                doc = await self.collection.find_one({"_id": obj_id})
                if doc:
                    # Convert ObjectIds to strings before creating model instance
                    converted_doc = self._convert_doc_ids_to_strings(doc)
                    return self.model_class(**converted_doc)
            except:
                pass

            # Fall back to string ID
            doc = await self.collection.find_one({"_id": entity_id})
            if doc:
                # Convert ObjectIds to strings before creating model instance
                converted_doc = self._convert_doc_ids_to_strings(doc)
                return self.model_class(**converted_doc)
            return None
        except Exception as e:
            logger.error(
                f"Failed to get {self.model_class.__name__} by ID {entity_id}: {e}"
            )
            return None

    async def update(self, entity_id: str, data: UpdateT) -> Optional[T]:
        """Update entity."""
        try:
            # Try ObjectId first for backwards compatibility
            update_filter = None
            try:
                obj_id = ObjectId(entity_id)
                update_filter = {"_id": obj_id}
            except:
                update_filter = {"_id": entity_id}

            update_data = self._convert_to_dict(data)
            update_data = self._add_timestamps(update_data, is_update=True)

            result = await self.collection.update_one(
                update_filter, {"$set": update_data}
            )

            if result.modified_count > 0:
                return await self.get_by_id(entity_id)
            return None
        except Exception as e:
            logger.error(
                f"Failed to update {self.model_class.__name__} {entity_id}: {e}"
            )
            return None

    async def update_fields(
        self, entity_id: str, fields: Dict[str, Any]
    ) -> Optional[T]:
        """Update specific entity fields."""
        try:
            # Try ObjectId first for backwards compatibility
            update_filter = None
            try:
                obj_id = ObjectId(entity_id)
                update_filter = {"_id": obj_id}
            except:
                update_filter = {"_id": entity_id}

            update_data = self._add_timestamps(fields.copy(), is_update=True)

            result = await self.collection.update_one(
                update_filter, {"$set": update_data}
            )

            if result.modified_count > 0:
                return await self.get_by_id(entity_id)
            return None
        except Exception as e:
            logger.error(
                f"Failed to update {self.model_class.__name__} fields {entity_id}: {e}"
            )
            return None

    async def delete(self, entity_id: str) -> bool:
        """Soft delete entity by setting deleted_at."""
        try:
            # Try ObjectId first for backwards compatibility
            delete_filter = None
            try:
                obj_id = ObjectId(entity_id)
                delete_filter = {"_id": obj_id}
            except:
                delete_filter = {"_id": entity_id}

            result = await self.collection.update_one(
                delete_filter,
                {
                    "$set": {
                        "is_active": False,
                        "deleted_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"Soft deleted {self.model_class.__name__} {entity_id}")
            return success
        except Exception as e:
            logger.error(
                f"Failed to delete {self.model_class.__name__} {entity_id}: {e}"
            )
            return False

    async def hard_delete(self, entity_id: str) -> bool:
        """Permanently delete entity from database."""
        try:
            # Try ObjectId first for backwards compatibility
            delete_filter = None
            try:
                obj_id = ObjectId(entity_id)
                delete_filter = {"_id": obj_id}
            except:
                delete_filter = {"_id": entity_id}

            result = await self.collection.delete_one(delete_filter)
            success = result.deleted_count > 0
            if success:
                logger.info(f"Hard deleted {self.model_class.__name__} {entity_id}")
            return success
        except Exception as e:
            logger.error(
                f"Failed to hard delete {self.model_class.__name__} {entity_id}: {e}"
            )
            return False

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination (excludes deleted)."""
        try:
            cursor = (
                self.collection.find({"deleted_at": None})
                .skip(skip)
                .limit(limit)
                .sort("created_at", -1)
            )

            entities = []
            async for doc in cursor:
                # Convert ObjectIds to strings before creating model instance
                converted_doc = self._convert_doc_ids_to_strings(doc)
                entities.append(self.model_class(**converted_doc))
            return entities
        except Exception as e:
            logger.error(f"Failed to get all {self.model_class.__name__}: {e}")
            return []

    async def count_all(self) -> int:
        """Count total entities (excludes deleted)."""
        try:
            return await self.collection.count_documents({"deleted_at": None})
        except Exception as e:
            logger.error(f"Failed to count {self.model_class.__name__}: {e}")
            return 0

    async def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort_field: str = "created_at",
        sort_direction: int = -1,
    ) -> List[T]:
        """Find entities by criteria."""
        try:
            cursor = (
                self.collection.find(criteria)
                .skip(skip)
                .limit(limit)
                .sort(sort_field, sort_direction)
            )

            entities = []
            async for doc in cursor:
                # Convert ObjectIds to strings before creating model instance
                converted_doc = self._convert_doc_ids_to_strings(doc)
                entities.append(self.model_class(**converted_doc))
            return entities
        except Exception as e:
            logger.error(f"Failed to find {self.model_class.__name__} by criteria: {e}")
            return []
