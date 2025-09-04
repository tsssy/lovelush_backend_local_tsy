"""Matching service for handling individual match records and chatroom creation."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.core.exceptions.exceptions import (
    NotFoundError,
    ResourceConflictError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.utils.datetime_utils import safe_isoformat, safe_isoformat_or_now
from app.domain.models.agent import Agent, SubAccount
from app.domain.models.chatroom import (
    ChatRequest,
    Chatroom,
    ChatroomCreate,
    ChatroomResponse,
    MatchBreakdown,
    MatchCandidate,
    MatchRecordUpdate,
    MatchResponse,
    MatchStatus,
    MatchSummary,
    MatchType,
)
from app.domain.models.credits import TransactionReason
from app.domain.services.app_settings_service import AppSettingsService
from app.domain.services.credits_service import CreditsService
from app.infrastructure.database.repositories.agent_repository import AgentRepository
from app.infrastructure.database.repositories.chatroom_repository import (
    ChatroomRepository,
)
from app.infrastructure.database.repositories.match_repository import (
    MatchRecordRepository,
)
from app.integrations.pusher.chatroom_service import ChatroomPusherService

logger = get_logger(__name__)


class MatchingService:
    """Service for handling individual match records and matching business logic."""

    def __init__(
        self,
        agent_repository: Optional[AgentRepository] = None,
        chatroom_repository: Optional[ChatroomRepository] = None,
        credits_service: Optional[CreditsService] = None,
        match_record_repository: Optional[MatchRecordRepository] = None,
        chatroom_pusher_service: Optional[ChatroomPusherService] = None,
        app_settings_service: Optional[AppSettingsService] = None,
    ) -> None:
        """Initialize MatchingService with required dependencies."""
        self.agent_repository = agent_repository or AgentRepository()
        self.chatroom_repository = chatroom_repository or ChatroomRepository()
        self.credits_service = credits_service or CreditsService()
        self.match_record_repository = (
            match_record_repository or MatchRecordRepository()
        )
        self.chatroom_pusher_service = (
            chatroom_pusher_service or ChatroomPusherService()
        )
        self.app_settings_service = app_settings_service or AppSettingsService()

    async def get_current_matches(self, user_id: str) -> MatchResponse:
        """
        Get user's current available matches with breakdown by type.

        Returns all available matches (initial, daily_free, paid) that user can use,
        aggregated into a single response for frontend compatibility.

        Args:
            user_id: User ID to get current matches for

        Returns:
            MatchResponse with available candidates and match breakdown metadata
        """
        logger.info(f"Getting current matches for user {user_id}")

        try:
            # Get user's credits for response
            user_credits_response = (
                await self.credits_service.get_or_create_user_credits(user_id)
            )

            # Get all available matches
            available_matches = (
                await self.match_record_repository.get_available_matches(
                    user_id, limit=100
                )
            )

            # Convert matches to candidates for frontend
            candidates = []
            for match in available_matches:
                candidate = await self._create_candidate_from_match(match)
                if candidate:
                    candidates.append(candidate)

            # If no available matches, include last match for UI context
            if not candidates:
                last_matches = (
                    await self.match_record_repository.get_user_match_history(
                        user_id, limit=1
                    )
                )
                if last_matches:
                    last_candidate = await self._create_candidate_from_match(
                        last_matches[0], is_last_match=True
                    )
                    if last_candidate:
                        candidates.append(last_candidate)

            # Get match breakdown for metadata
            breakdown = await self._get_match_breakdown(user_id)
            summary = await self._get_match_summary(user_id)

            # Determine if we're showing available matches or last match
            showing_last_match = len(available_matches) == 0 and len(candidates) > 0

            response = MatchResponse(
                candidates=candidates,
                credits_consumed=0,
                remaining_credits=user_credits_response.current_balance,
                has_remaining_matches=len(available_matches) > 0,
                metadata={
                    "match_breakdown": breakdown.model_dump(),
                    "match_summary": summary.model_dump(),
                    "source": "current_matches",
                    "showing_last_match": showing_last_match,
                    "available_matches_count": len(available_matches),
                },
            )

            logger.info(
                f"Returning {len(candidates)} available matches for user {user_id}"
            )
            return response

        except Exception as e:
            logger.error(f"Failed to get current matches for user {user_id}: {e}")
            # Return empty response on error
            return MatchResponse(
                candidates=[],
                credits_consumed=0,
                remaining_credits=0,
                has_remaining_matches=False,
                metadata={"error": str(e)},
            )

    async def request_new_matches(
        self, user_id: str, use_paid_match: bool = False
    ) -> MatchResponse:
        """
        Request new matches for a user using the new individual record system.

        Logic (simplified):
        1. Check if user has initial matches available → grant if first time
        2. Check if user can get daily free match → grant if available
        3. If use_paid_match=true → grant paid match
        4. Otherwise → error (no free matches available)

        Args:
            user_id: User ID requesting new matches
            use_paid_match: Whether to use paid match if no free matches available

        Returns:
            MatchResponse with new matches granted

        Raises:
            ValueError: If no free matches available and use_paid_match=False
            ValidationError: If insufficient credits for paid match
        """
        logger.info(
            f"Requesting new matches for user {user_id}, use_paid_match={use_paid_match}"
        )

        try:
            # Get user's credits
            await self.credits_service.get_or_create_user_credits(user_id)

            # Check if user has any available matches first
            available_matches = (
                await self.match_record_repository.get_available_matches(
                    user_id, limit=1
                )
            )
            if available_matches:
                logger.info(
                    f"User {user_id} already has available matches, returning those"
                )
                return await self.get_current_matches(user_id)

            # Try to grant matches in order of priority

            # 1. Initial matches (first-time user bonus)
            if await self._can_grant_initial_matches(user_id):
                return await self._grant_initial_matches(user_id)

            # 2. Daily free match
            if await self._can_grant_daily_free_match(user_id):
                return await self._grant_daily_free_match(user_id)

            # 3. Paid match (if requested)
            if use_paid_match:
                return await self._grant_paid_match(user_id)

            # 4. No matches available
            raise NotFoundError(
                "No free matches available. Set use_paid_match=true to get paid matches."
            )

        except (ValueError, ValidationError):
            # Re-raise business logic errors
            raise
        except Exception as e:
            logger.error(f"Failed to request new matches for user {user_id}: {e}")
            raise ValueError(f"Failed to process match request: {e}")

    async def consume_match(self, user_id: str, sub_account_id: str) -> bool:
        """
        Consume a match when user starts chatting with a candidate.

        Args:
            user_id: User ID consuming the match
            sub_account_id: Sub-account ID being matched with

        Returns:
            True if match was consumed successfully
        """
        try:
            # Find the available match for this candidate
            match = await self.match_record_repository.get_match_by_candidate(
                user_id, sub_account_id
            )

            if not match:
                logger.warning(
                    f"No available match found for user {user_id} and candidate {sub_account_id}"
                )
                return False

            # Consume the match
            success = await self.match_record_repository.consume_match(
                str(match.id), user_id
            )

            if success:
                logger.info(
                    f"Match consumed: user {user_id} matched with {sub_account_id}"
                )

            return success

        except Exception as e:
            logger.error(
                f"Failed to consume match for user {user_id} and candidate {sub_account_id}: {e}"
            )
            return False

    async def _create_candidate_from_match(
        self, match, is_last_match: bool = False
    ) -> Optional[MatchCandidate]:
        """Create a MatchCandidate from a match record."""
        try:
            # Fetch live candidate data from sub-account
            sub_account = await self.agent_repository.get_sub_account_by_id(
                match.sub_account_id
            )

            if sub_account and sub_account.is_active:
                # Get agent name
                agent = await self.agent_repository.get_by_id(str(sub_account.agent_id))
                agent_name = agent.name if agent else "Unknown Agent"

                # Create candidate with live data including match metadata
                candidate = MatchCandidate(
                    sub_account_id=str(sub_account.id),
                    agent_id=str(sub_account.agent_id),
                    agent_name=agent_name,
                    sub_account_name=sub_account.name,
                    display_name=sub_account.display_name,
                    avatar_url=sub_account.avatar_url,
                    bio=sub_account.bio,
                    age=sub_account.age,
                    location=sub_account.location,
                    tags=sub_account.tags or [],
                    photo_urls=sub_account.photo_urls or [],
                    match_id=str(match.id),
                    match_type=match.match_type,
                )
                return candidate
            else:
                # Sub-account no longer available
                if not is_last_match:
                    # Only mark as expired if it's an active match
                    logger.warning(
                        f"Sub-account {match.sub_account_id} no longer available for match {match.id}, marking as expired"
                    )
                    await self.match_record_repository.update(
                        str(match.id), MatchRecordUpdate(status=MatchStatus.EXPIRED)
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to create candidate from match {match.id}: {e}")
            return None

    # Private methods for match granting

    async def _can_grant_initial_matches(self, user_id: str) -> bool:
        """Check if user can receive initial matches."""
        try:
            # Check if user has ever received initial matches
            counts = await self.match_record_repository.get_match_counts_by_type(
                user_id
            )
            initial_count = counts.get(MatchType.INITIAL, {}).get("total", 0)

            return initial_count == 0  # Never received initial matches

        except Exception as e:
            logger.error(
                f"Failed to check initial matches eligibility for user {user_id}: {e}"
            )
            return False

    async def _can_grant_daily_free_match(self, user_id: str) -> bool:
        """Check if user can receive daily free match."""
        try:
            return not await self.match_record_repository.has_daily_match_today(user_id)
        except Exception as e:
            logger.error(
                f"Failed to check daily match eligibility for user {user_id}: {e}"
            )
            return False

    async def _grant_initial_matches(self, user_id: str) -> MatchResponse:
        """Grant initial matches to first-time user."""
        try:
            match_config = await self.app_settings_service.get_match_config()
            initial_count = match_config.initial_free_matches

            # Get candidates for initial matches
            candidates = await self._get_round_robin_candidates(
                count=initial_count, user_id=user_id
            )
            if not candidates:
                raise ValueError("No candidates available for initial matches")

            # Convert candidates to sub_account_ids for storage
            sub_account_ids = [candidate.sub_account_id for candidate in candidates]

            # Grant individual match records
            matches = await self.match_record_repository.grant_initial_matches(
                user_id, sub_account_ids, credits_per_match=0
            )

            # Get updated user credits
            user_credits_response = (
                await self.credits_service.get_or_create_user_credits(user_id)
            )

            logger.info(f"Granted {len(matches)} initial matches to user {user_id}")

            return MatchResponse(
                candidates=candidates,
                credits_consumed=0,
                remaining_credits=user_credits_response.current_balance,
                has_remaining_matches=True,
                metadata={
                    "source": "initial_matches",
                    "match_type": MatchType.INITIAL,
                    "matches_granted": len(matches),
                },
            )

        except Exception as e:
            logger.error(f"Failed to grant initial matches to user {user_id}: {e}")
            raise

    async def _grant_daily_free_match(self, user_id: str) -> MatchResponse:
        """Grant daily free match to user."""
        try:
            # Get one candidate for daily match
            candidates = await self._get_round_robin_candidates(
                count=1, user_id=user_id
            )
            if not candidates:
                raise ValueError("No candidates available for daily free match")

            candidate_sub_account_id = candidates[0].sub_account_id

            # Set expiration to end of day
            tomorrow = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)

            # Grant daily free match
            match = await self.match_record_repository.grant_daily_free_match(
                user_id, candidate_sub_account_id, expires_at=tomorrow
            )

            # Get updated user credits
            user_credits_response = (
                await self.credits_service.get_or_create_user_credits(user_id)
            )

            logger.info(f"Granted daily free match to user {user_id}")

            return MatchResponse(
                candidates=candidates,
                credits_consumed=0,
                remaining_credits=user_credits_response.current_balance,
                has_remaining_matches=True,
                metadata={
                    "source": "daily_free_match",
                    "match_type": MatchType.DAILY_FREE,
                    "expires_at": tomorrow.isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Failed to grant daily free match to user {user_id}: {e}")
            raise

    async def _grant_paid_match(self, user_id: str) -> MatchResponse:
        """Grant paid match to user."""
        try:
            match_config = await self.app_settings_service.get_match_config()
            cost_per_match = match_config.cost_per_match

            # Check if user has enough credits
            user_credits_response = (
                await self.credits_service.get_or_create_user_credits(user_id)
            )
            if user_credits_response.current_balance < cost_per_match:
                raise ResourceConflictError(
                    f"Insufficient credits. Need {cost_per_match}, have {user_credits_response.current_balance}"
                )

            # Get one candidate for paid match
            candidates = await self._get_round_robin_candidates(
                count=1, user_id=user_id
            )
            if not candidates:
                raise NotFoundError("No candidates available for paid match")

            candidate_sub_account_id = candidates[0].sub_account_id

            # Consume credits first
            success = await self.credits_service.consume_credits(
                user_id=user_id,
                amount=cost_per_match,
                reason=TransactionReason.MATCH_CONSUMPTION,
                description="Paid match request",
            )

            if not success:
                raise ValueError("Failed to process payment for paid match")

            # Grant paid match
            match = await self.match_record_repository.grant_paid_match(
                user_id, candidate_sub_account_id, credits_consumed=cost_per_match
            )

            # Get updated user credits
            updated_credits = await self.credits_service.get_user_credits(user_id)
            remaining_credits = (
                updated_credits.current_balance if updated_credits else 0
            )

            logger.info(
                f"Granted paid match to user {user_id} for {cost_per_match} credits"
            )

            return MatchResponse(
                candidates=candidates,
                credits_consumed=cost_per_match,
                remaining_credits=remaining_credits,
                has_remaining_matches=True,
                metadata={
                    "source": "paid_match",
                    "match_type": MatchType.PAID,
                    "credits_consumed": cost_per_match,
                },
            )

        except Exception as e:
            logger.error(f"Failed to grant paid match to user {user_id}: {e}")
            raise

    async def _get_match_breakdown(self, user_id: str) -> MatchBreakdown:
        """Get breakdown of available matches by type."""
        try:
            available_initial = len(
                await self.match_record_repository.get_available_matches_by_type(
                    user_id, MatchType.INITIAL
                )
            )
            available_daily_free = len(
                await self.match_record_repository.get_available_matches_by_type(
                    user_id, MatchType.DAILY_FREE
                )
            )
            available_paid = len(
                await self.match_record_repository.get_available_matches_by_type(
                    user_id, MatchType.PAID
                )
            )

            total = available_initial + available_daily_free + available_paid

            return MatchBreakdown(
                initial=available_initial,
                daily_free=available_daily_free,
                paid=available_paid,
                total=total,
            )

        except Exception as e:
            logger.error(f"Failed to get match breakdown for user {user_id}: {e}")
            return MatchBreakdown()

    async def _get_match_summary(self, user_id: str) -> MatchSummary:
        """Get summary of user's match status."""
        try:
            breakdown = await self._get_match_breakdown(user_id)

            # Check eligibility for new matches
            can_get_initial = await self._can_grant_initial_matches(user_id)
            can_get_daily = await self._can_grant_daily_free_match(user_id)

            # Get total matches consumed
            total_consumed = (
                await self.match_record_repository.get_total_matches_consumed(user_id)
            )

            return MatchSummary(
                available_matches=breakdown,
                has_initial_matches=can_get_initial,
                can_get_daily_free=can_get_daily,
                total_matches_used=total_consumed,
                last_daily_match_date=None,  # TODO: Add daily match date tracking
            )

        except Exception as e:
            logger.error(f"Failed to get match summary for user {user_id}: {e}")
            return MatchSummary(
                available_matches=MatchBreakdown(),
                has_initial_matches=False,
                can_get_daily_free=False,
                total_matches_used=0,
                last_daily_match_date=None,
            )

    # Candidate selection methods (simplified - keeping existing logic for now)

    async def _get_round_robin_candidates(
        self, count: int = 5, user_id: Optional[str] = None
    ) -> List[MatchCandidate]:
        """Get match candidates using user-aware round-robin algorithm."""
        if not user_id:
            # Fallback to basic algorithm
            return await self._get_basic_candidates(count)

        # Get all active agents, ordered by priority
        agents = await self.agent_repository.get_active_agents()
        if not agents:
            return []

        # Get user's match history to avoid duplicates
        user_matches = await self.match_record_repository.get_user_match_history(
            user_id, limit=100
        )
        used_candidates = set()

        for match in user_matches:
            if hasattr(match, "sub_account_id") and match.sub_account_id:
                used_candidates.add(match.sub_account_id)

        # Calculate agent starting offset based on user to ensure fair distribution
        user_hash = hash(user_id)
        agent_start_offset = user_hash % len(agents)

        candidates = []
        max_rounds = 5  # Increased to handle single agent with multiple sub_accounts

        for round_num in range(max_rounds):
            round_candidates = await self._get_candidates_from_user_aware_round(
                agents, agent_start_offset, used_candidates, round_num
            )
            candidates.extend(round_candidates)

            # Stop if we have enough candidates or no more available
            if len(candidates) >= count or not round_candidates:
                break

        return candidates[:count]

    async def _get_basic_candidates(self, count: int = 5) -> List[MatchCandidate]:
        """Basic candidate selection algorithm."""
        # Get all active agents, ordered by priority
        agents = await self.agent_repository.get_active_agents()
        if not agents:
            return []

        candidates = []
        max_rounds = 5  # Increased to handle single agent with multiple sub_accounts

        for _ in range(max_rounds):
            round_candidates = await self._get_candidates_from_round(agents)
            candidates.extend(round_candidates)

            # Stop if we have enough candidates or no more available
            if len(candidates) >= count or not round_candidates:
                break

        return candidates[:count]

    async def _get_candidates_from_user_aware_round(
        self,
        agents: List[Agent],
        agent_start_offset: int,
        used_candidates: set,
        round_num: int,
    ) -> List[MatchCandidate]:
        """Get candidates from one round using user-aware distribution."""
        round_candidates = []

        # Reorder agents based on user's starting offset
        reordered_agents = agents[agent_start_offset:] + agents[:agent_start_offset]

        # Get available sub-accounts for each agent in parallel
        agent_sub_accounts = await asyncio.gather(
            *[
                self.agent_repository.get_available_sub_accounts_by_agent(str(agent.id))
                for agent in reordered_agents
            ]
        )

        for agent, sub_accounts in zip(reordered_agents, agent_sub_accounts):
            if not sub_accounts:
                continue

            # For user-aware distribution, select sub-account based on round number
            selected_sub_account = None

            # Try to find a sub-account this user hasn't used yet
            for i in range(len(sub_accounts)):
                candidate_index = (round_num + i) % len(sub_accounts)
                candidate_sub_account = sub_accounts[candidate_index]

                if str(candidate_sub_account.id) not in used_candidates:
                    selected_sub_account = candidate_sub_account
                    break

            # If all sub-accounts have been used, cycle through them anyway
            if not selected_sub_account and sub_accounts:
                candidate_index = round_num % len(sub_accounts)
                selected_sub_account = sub_accounts[candidate_index]

            if selected_sub_account:
                # Create candidate
                candidate = MatchCandidate(
                    sub_account_id=str(selected_sub_account.id),
                    agent_id=str(agent.id),
                    agent_name=agent.name,
                    sub_account_name=selected_sub_account.name,
                    display_name=selected_sub_account.display_name,
                    avatar_url=selected_sub_account.avatar_url,
                    bio=selected_sub_account.bio,
                    age=selected_sub_account.age,
                    location=selected_sub_account.location,
                    tags=selected_sub_account.tags or [],
                    photo_urls=selected_sub_account.photo_urls or [],
                )
                round_candidates.append(candidate)

        return round_candidates

    async def _get_candidates_from_round(
        self, agents: List[Agent]
    ) -> List[MatchCandidate]:
        """Get candidates from one round of round-robin across all agents."""
        round_candidates = []

        # Get available sub-accounts for each agent in parallel
        agent_sub_accounts = await asyncio.gather(
            *[
                self.agent_repository.get_available_sub_accounts_by_agent(str(agent.id))
                for agent in agents
            ]
        )

        for agent, sub_accounts in zip(agents, agent_sub_accounts):
            if not sub_accounts:
                continue

            # Round-robin within agent's sub-accounts
            next_index = (agent.last_assigned_sub_account_index + 1) % len(sub_accounts)
            selected_sub_account = sub_accounts[next_index]

            # Create candidate
            candidate = MatchCandidate(
                sub_account_id=str(selected_sub_account.id),
                agent_id=str(agent.id),
                agent_name=agent.name,
                sub_account_name=selected_sub_account.name,
                display_name=selected_sub_account.display_name,
                avatar_url=selected_sub_account.avatar_url,
                bio=selected_sub_account.bio,
                age=selected_sub_account.age,
                location=selected_sub_account.location,
                tags=selected_sub_account.tags or [],
                photo_urls=selected_sub_account.photo_urls or [],
            )
            round_candidates.append(candidate)

            # Update agent's last assigned index
            await self.agent_repository.update_agent_last_assigned_index(
                str(agent.id), next_index
            )

        return round_candidates

    # Chatroom creation methods (keeping existing logic)

    async def create_chat(self, chat_request: ChatRequest) -> ChatroomResponse:
        """Create or get existing chatroom between user and sub-account."""
        user_id = chat_request.user_id
        sub_account_id = chat_request.sub_account_id

        # Check if chatroom already exists (idempotent behavior)
        existing_chatroom = await self.chatroom_repository.get_existing_chatroom(
            user_id, sub_account_id
        )

        if existing_chatroom:
            logger.info(
                f"Found existing chatroom {existing_chatroom.id} for user {user_id} and sub-account {sub_account_id}"
            )
            response = self._to_chatroom_response(existing_chatroom)
            response.metadata = {
                **response.metadata,
                "chatroom_created": False,
                "chatroom_existed": True,
            }
            return response

        # SECURITY: Verify user has a match for this candidate
        match = await self.match_record_repository.get_match_by_candidate(
            user_id, sub_account_id
        )

        if not match:
            logger.warning(
                f"User {user_id} attempted to create chat with unauthorized sub-account {sub_account_id}"
            )
            raise ValidationError(
                "Cannot create chatroom with this sub-account. No available match found."
            )

        # Get sub-account to validate and get agent_id
        sub_account = await self.agent_repository.get_sub_account_by_id(sub_account_id)
        if not sub_account:
            raise NotFoundError(f"SubAccount {sub_account_id} not found")

        if not sub_account.is_active or sub_account.status != "available":
            raise ValueError(f"SubAccount {sub_account_id} is not available")

        if sub_account.current_chat_count >= sub_account.max_concurrent_chats:
            raise ValueError(f"SubAccount {sub_account_id} is at capacity")

        # Create new chatroom
        chatroom_create = ChatroomCreate(
            user_id=user_id,
            sub_account_id=sub_account_id,
            agent_id=str(sub_account.agent_id),
            channel_name="",  # Will be set in repository based on chatroom ID
        )

        chatroom = await self.chatroom_repository.create_chatroom(chatroom_create)

        # Increment sub-account chat count
        await self.agent_repository.increment_sub_account_chat_count(sub_account_id)

        # Consume the match
        await self.consume_match(user_id, sub_account_id)

        # Send real-time match notifications to both user and agent
        await self._send_match_created_notifications(
            chatroom, user_id, sub_account_id, sub_account
        )

        logger.info(
            f"Created new chatroom {chatroom.id} for user {user_id} and sub-account {sub_account_id}"
        )

        response = self._to_chatroom_response(chatroom)
        response.metadata = {
            **response.metadata,
            "chatroom_created": True,
            "chatroom_existed": False,
        }
        return response

    async def end_chat(self, chatroom_id: str) -> bool:
        """End a chatroom and decrement sub-account chat count."""
        # Get chatroom
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom or chatroom.status != "active":
            return False

        # End chatroom
        success = await self.chatroom_repository.end_chatroom(chatroom_id)
        if success:
            # Decrement sub-account chat count
            await self.agent_repository.decrement_sub_account_chat_count(
                str(chatroom.sub_account_id)
            )

        return success

    async def get_user_match_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get user's match history with individual match records.

        Args:
            user_id: User ID to get match history for
            limit: Maximum number of records to return

        Returns:
            List of match record dictionaries
        """
        try:
            match_records = await self.match_record_repository.get_user_match_history(
                user_id, limit
            )

            # Convert to response format
            history = []
            for record in match_records:
                # Get live candidate data for the response
                candidate_data = None
                sub_account = await self.agent_repository.get_sub_account_by_id(
                    record.sub_account_id
                )
                if sub_account:
                    # Get agent name
                    agent = await self.agent_repository.get_by_id(
                        str(sub_account.agent_id)
                    )
                    agent_name = agent.name if agent else "Unknown Agent"

                    candidate_data = {
                        "sub_account_id": str(sub_account.id),
                        "agent_id": str(sub_account.agent_id),
                        "agent_name": agent_name,
                        "sub_account_name": sub_account.name,
                        "display_name": sub_account.display_name,
                        "avatar_url": sub_account.avatar_url,
                        "bio": sub_account.bio,
                        "age": sub_account.age,
                        "location": sub_account.location,
                        "tags": sub_account.tags or [],
                        "photo_urls": sub_account.photo_urls or [],
                    }
                else:
                    # Sub-account no longer exists, show minimal info
                    candidate_data = {
                        "sub_account_id": record.sub_account_id,
                        "agent_id": None,
                        "agent_name": "Unavailable",
                        "sub_account_name": "Unavailable",
                        "display_name": "Unavailable",
                        "avatar_url": None,
                        "bio": None,
                        "age": None,
                        "location": None,
                        "tags": [],
                        "photo_urls": [],
                    }

                history.append(
                    {
                        "id": str(record.id),
                        "match_type": record.match_type,
                        "candidate": candidate_data,
                        "status": record.status,
                        "credits_consumed": record.credits_consumed,
                        "consumed_at": (safe_isoformat(record.consumed_at)),
                        "expires_at": (safe_isoformat(record.expires_at)),
                        "created_at": (safe_isoformat(record.created_at)),
                    }
                )

            logger.info(f"Retrieved {len(history)} match records for user {user_id}")
            return history

        except Exception as e:
            logger.error(f"Failed to get match history for user {user_id}: {e}")
            return []

    def _to_chatroom_response(self, chatroom: Chatroom) -> ChatroomResponse:
        """Convert Chatroom model to ChatroomResponse."""
        return ChatroomResponse(
            _id=chatroom.id,
            user_id=str(chatroom.user_id),
            sub_account_id=str(chatroom.sub_account_id),
            agent_id=str(chatroom.agent_id),
            status=chatroom.status,
            channel_name=chatroom.channel_name,
            metadata=chatroom.metadata,
            started_at=chatroom.started_at,
            ended_at=chatroom.ended_at,
            last_activity_at=chatroom.last_activity_at,
            created_at=chatroom.created_at,
            updated_at=chatroom.updated_at,
        )

    async def _send_match_created_notifications(
        self,
        chatroom: Chatroom,
        user_id: str,
        sub_account_id: str,
        sub_account: SubAccount,
    ) -> None:
        """Send real-time match.created notifications to both user and agent."""
        try:
            # Prepare the match notification payload
            match_payload = {
                "conversation_id": str(chatroom.id),
                "dm_channel": chatroom.channel_name,
                "peer": {
                    "id": sub_account_id,
                    "name": sub_account.name,
                    "display_name": sub_account.display_name,
                    "avatar_url": sub_account.avatar_url,
                    "bio": sub_account.bio,
                    "age": sub_account.age,
                    "location": sub_account.location,
                    "tags": sub_account.tags or [],
                    "photo_urls": sub_account.photo_urls or [],
                    "type": "agent",
                },
                "created_at": safe_isoformat_or_now(chatroom.created_at),
                "status": "active",
            }

            # Send notification to user on private-user-{user_id}
            user_channel = f"private-user-{user_id}"
            self.chatroom_pusher_service.pusher_client.trigger(
                user_channel, "match.created", match_payload
            )
            logger.info(
                f"Sent match.created notification to user {user_id} on channel {user_channel}"
            )

            # Prepare agent notification payload (peer is the user)
            agent_match_payload = {
                "conversation_id": str(chatroom.id),
                "dm_channel": chatroom.channel_name,
                "peer": {
                    "id": user_id,
                    "name": f"User {user_id}",  # Could be enhanced with actual user name
                    "display_name": f"User {user_id}",
                    "avatar_url": None,
                    "type": "user",
                },
                "created_at": safe_isoformat_or_now(chatroom.created_at),
                "status": "active",
            }

            # Send notification to agent on private-agent-{agent_id}
            agent_channel = f"private-agent-{sub_account.agent_id}"
            self.chatroom_pusher_service.pusher_client.trigger(
                agent_channel, "match.created", agent_match_payload
            )
            logger.info(
                f"Sent match.created notification to agent {sub_account.agent_id} on channel {agent_channel}"
            )

        except Exception as e:
            logger.error(f"Failed to send match notifications: {e}")
            # Don't raise - this shouldn't block chatroom creation
