"""Workflow repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.core.logging import get_logger
from app.domain.models.user import PyObjectId
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)
from app.interfaces.telegram.models.workflow import (
    WorkflowState,
    WorkflowStateCreate,
    WorkflowStateUpdate,
    WorkflowStep,
)

logger = get_logger(__name__)


class WorkflowRepositoryInterface(
    BaseRepositoryInterface[WorkflowState, WorkflowStateCreate, WorkflowStateUpdate]
):
    """Workflow repository interface with domain-specific methods."""

    async def get_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int
    ) -> Optional[WorkflowState]:
        """Get workflow state by telegram user ID and chat ID."""
        raise NotImplementedError

    async def update_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int, workflow_update: WorkflowStateUpdate
    ) -> Optional[WorkflowState]:
        """Update workflow state by telegram user and chat."""
        raise NotImplementedError

    async def update_step_and_data(
        self,
        telegram_user_id: int,
        chat_id: int,
        step: WorkflowStep,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[WorkflowState]:
        """Update workflow step and optionally merge data."""
        raise NotImplementedError

    async def delete_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int
    ) -> bool:
        """Delete workflow state by telegram user ID and chat ID."""
        raise NotImplementedError

    async def get_expired_workflows(self) -> List[WorkflowState]:
        """Get all expired workflow states."""
        raise NotImplementedError

    async def cleanup_expired_workflows(self) -> int:
        """Delete expired workflow states and return count."""
        raise NotImplementedError


class WorkflowRepository(
    BaseRepository[WorkflowState, WorkflowStateCreate, WorkflowStateUpdate],
    WorkflowRepositoryInterface,
):
    """MongoDB workflow repository implementation."""

    def __init__(self):
        super().__init__("workflow_states", WorkflowState)

    async def create(self, data: WorkflowStateCreate) -> WorkflowState:
        """Create a new workflow state."""
        try:
            workflow_dict = data.model_dump()

            # Ensure enum is stored as string value before creating WorkflowState
            if isinstance(workflow_dict.get("current_step"), WorkflowStep):
                workflow_dict["current_step"] = workflow_dict["current_step"].value

            workflow_dict = self._add_timestamps(workflow_dict)

            # Create the WorkflowState instance first (it will keep user_id as string)
            workflow = WorkflowState(**workflow_dict)

            # For database insertion, convert user_id to ObjectId
            db_dict = workflow.model_dump(by_alias=True, exclude={"id"})
            db_dict["user_id"] = ObjectId(workflow.user_id)

            # Ensure enum is string for database storage
            if "current_step" in db_dict and isinstance(
                db_dict["current_step"], WorkflowStep
            ):
                db_dict["current_step"] = db_dict["current_step"].value

            result = await self.collection.insert_one(db_dict)
            workflow.id = PyObjectId(result.inserted_id)

            logger.info(f"Workflow state created with ID: {workflow.id}")
            return workflow
        except Exception as e:
            logger.error(f"Failed to create workflow state: {e}")
            raise

    async def get_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int
    ) -> Optional[WorkflowState]:
        """Get workflow state by telegram user ID and chat ID."""
        try:
            workflow_doc = await self.collection.find_one(
                {"telegram_user_id": telegram_user_id, "chat_id": chat_id}
            )
            return WorkflowState(**workflow_doc) if workflow_doc else None
        except Exception as e:
            logger.error(
                f"Failed to get workflow by telegram_user {telegram_user_id} and chat {chat_id}: {e}"
            )
            return None

    async def get_by_id(self, entity_id: str) -> Optional[WorkflowState]:
        """Get workflow state by ID."""
        try:
            workflow_doc = await self.collection.find_one({"_id": ObjectId(entity_id)})
            return WorkflowState(**workflow_doc) if workflow_doc else None
        except Exception as e:
            logger.error(f"Failed to get workflow by ID {entity_id}: {e}")
            return None

    async def update_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int, workflow_update: WorkflowStateUpdate
    ) -> Optional[WorkflowState]:
        """Update workflow state."""
        try:
            update_data = workflow_update.model_dump(
                exclude_unset=True, exclude_none=True
            )
            if not update_data:
                return None

            # Ensure enum is stored as string value
            if "current_step" in update_data and isinstance(
                update_data["current_step"], WorkflowStep
            ):
                update_data["current_step"] = update_data["current_step"].value

            update_data["updated_at"] = datetime.now(timezone.utc)

            result = await self.collection.find_one_and_update(
                {"telegram_user_id": telegram_user_id, "chat_id": chat_id},
                {"$set": update_data},
                return_document=True,
            )

            if result:
                logger.info(
                    f"Updated workflow for telegram_user {telegram_user_id} and chat {chat_id}"
                )
                return WorkflowState(**result)
            return None
        except Exception as e:
            logger.error(f"Failed to update workflow: {e}")
            return None

    async def update_step_and_data(
        self,
        telegram_user_id: int,
        chat_id: int,
        step: WorkflowStep,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[WorkflowState]:
        """Update workflow step and optionally merge data."""
        try:
            update_dict = {
                "current_step": step.value,  # Ensure enum is stored as string
                "updated_at": datetime.now(timezone.utc),
            }

            if data:
                # Merge new data with existing data
                existing_workflow = await self.get_by_user_and_chat(
                    telegram_user_id, chat_id
                )
                if existing_workflow:
                    merged_data = {**existing_workflow.data, **data}
                    update_dict["data"] = merged_data
                else:
                    update_dict["data"] = data

            result = await self.collection.find_one_and_update(
                {"telegram_user_id": telegram_user_id, "chat_id": chat_id},
                {"$set": update_dict},
                return_document=True,
            )

            if result:
                logger.info(
                    f"Updated workflow step for telegram_user {telegram_user_id} and chat {chat_id}"
                )
                return WorkflowState(**result)
            return None
        except Exception as e:
            logger.error(f"Failed to update workflow step and data: {e}")
            return None

    async def delete_by_user_and_chat(
        self, telegram_user_id: int, chat_id: int
    ) -> bool:
        """Delete workflow state by telegram user ID and chat ID."""
        try:
            result = await self.collection.delete_one(
                {"telegram_user_id": telegram_user_id, "chat_id": chat_id}
            )
            success = result.deleted_count > 0
            if success:
                logger.info(
                    f"Deleted workflow for telegram_user {telegram_user_id} and chat {chat_id}"
                )
            return success
        except Exception as e:
            logger.error(f"Failed to delete workflow: {e}")
            return False

    async def get_expired_workflows(self) -> List[WorkflowState]:
        """Get all expired workflow states."""
        try:
            now = datetime.now(timezone.utc)
            cursor = self.collection.find({"expires_at": {"$lt": now}})

            workflows = []
            async for doc in cursor:
                workflows.append(WorkflowState(**doc))
            return workflows
        except Exception as e:
            logger.error(f"Failed to get expired workflows: {e}")
            return []

    async def cleanup_expired_workflows(self) -> int:
        """Delete expired workflow states and return count of deleted documents."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.collection.delete_many({"expires_at": {"$lt": now}})
            count = result.deleted_count
            if count > 0:
                logger.info(f"Cleaned up {count} expired workflows")
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup expired workflows: {e}")
            return 0

    async def get_workflows_by_type(self, workflow_type: str) -> List[WorkflowState]:
        """Get all workflows of a specific type."""
        cursor = self.collection.find({"workflow_type": workflow_type})

        workflows = []
        async for doc in cursor:
            workflows.append(WorkflowState(**doc))

        return workflows

    async def get_completed_workflows(
        self, limit: Optional[int] = None
    ) -> List[WorkflowState]:
        """Get completed workflows for analysis."""
        query = {"current_step": WorkflowStep.COMPLETE.value}
        cursor = self.collection.find(query).sort("updated_at", -1)

        if limit:
            cursor = cursor.limit(limit)

        workflows = []
        async for doc in cursor:
            workflows.append(WorkflowState(**doc))

        return workflows

    async def get_user_workflow_history(self, user_id: int) -> List[WorkflowState]:
        """Get all workflows for a specific user."""
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", -1)

        workflows = []
        async for doc in cursor:
            workflows.append(WorkflowState(**doc))

        return workflows
