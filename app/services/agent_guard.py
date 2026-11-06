"""Agent Commerce Guard service for merchant policy enforcement."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Optional
import uuid
from sqlalchemy import func, select, update
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.currencies import get_currency_info
from app.models.agent import AgentProfileModel, AgentTransactionModel
from app.models.audit import AuditLogModel
from app.schemas.agent import (
    AgentDecision,
    AgentDecisionEnum,
    AgentProfile,
    AgentRegistration,
    AgentTransactionRequest,
)
from app.services.risk_engine import calculate_agent_risk


class AgentGuard:
    """Merchant-side policy and security engine for AI agent purchases."""

    _locks: dict[str, asyncio.Lock] = {}
    _locks_mutex = asyncio.Lock()

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the AgentGuard service with an active database session.

        Args:
            db: SQLAlchemy asynchronous database session.
        """
        self.db = db

    @classmethod
    async def _get_agent_lock(cls, agent_id: str) -> asyncio.Lock:
        async with cls._locks_mutex:
            if agent_id not in cls._locks:
                cls._locks[agent_id] = asyncio.Lock()
            return cls._locks[agent_id]

    @staticmethod
    def _compute_payload_hash(request: AgentTransactionRequest) -> str:
        """Compute a deterministic SHA-256 hash of core transaction parameters.

        Args:
            request: Inbound transaction request.

        Returns:
            str: Hexadecimal SHA-256 hash string.
        """
        normalized_data = {
            "agent_id": request.agent_id.strip(),
            "amount": format(request.amount.normalize(), "f"),
            "currency": request.currency.strip().upper(),
            "merchant_id": request.merchant_id.strip(),
            "merchant_name": (request.merchant_name or "").strip(),
            "category_mcc": (
                request.category_mcc.strip() if request.category_mcc else None
            ),
            "description": (request.description or "").strip(),
            "metadata": request.metadata or {},
        }
        serialized = json.dumps(normalized_data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    async def _log_audit(
        self, agent_id: str, event_type: str, details: dict[str, Any]
    ) -> None:
        """Append an event to the persistent audit log.

        Args:
            agent_id: ID of the agent associated with the event.
            event_type: Category identifier of the event.
            details: Contextual details of the audit action.
        """
        audit_entry = AuditLogModel(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            event_type=event_type,
            details=details,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit_entry)

    async def register_agent(self, registration: AgentRegistration) -> AgentProfile:
        """Register a new AI agent and store its initial spending policies.

        Args:
            registration: Agent registration payload containing spending rules.

        Returns:
            AgentProfile: The persisted agent profile.

        Raises:
            ValueError: If agent already exists or spending policies are invalid.
        """
        # Validate spending policies
        if registration.max_transaction_amount <= 0:
            raise ValueError("max_transaction_amount must be greater than zero")
        if registration.daily_spending_limit <= 0:
            raise ValueError("daily_spending_limit must be greater than zero")
        if not registration.allowed_currencies:
            raise ValueError("allowed_currencies must include at least one currency")
        if registration.daily_spending_limit < registration.max_transaction_amount:
            raise ValueError("daily_spending_limit cannot be less than max_transaction_amount")

        # Check for duplicate agent_id
        stmt = select(AgentProfileModel).where(
            AgentProfileModel.agent_id == registration.agent_id
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"Agent '{registration.agent_id}' is already registered")

        agent_model = AgentProfileModel(
            agent_id=registration.agent_id,
            name=registration.name,
            owner_id=registration.owner_id,
            description=registration.description,
            status="ACTIVE",
            max_transaction_amount=registration.max_transaction_amount,
            daily_spending_limit=registration.daily_spending_limit,
            allowed_currencies=registration.allowed_currencies,
            budget_currency=registration.budget_currency,
            allowed_merchants=registration.allowed_merchants,
            allowed_categories=registration.allowed_categories,
            requires_human_approval_above=registration.requires_human_approval_above,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(agent_model)

        await self._log_audit(
            agent_id=registration.agent_id,
            event_type="AGENT_REGISTERED",
            details={
                "name": registration.name,
                "owner_id": registration.owner_id,
                "max_transaction_amount": str(registration.max_transaction_amount),
                "daily_spending_limit": str(registration.daily_spending_limit),
                "allowed_currencies": registration.allowed_currencies,
                "budget_currency": registration.budget_currency,
            },
        )
        await self.db.commit()
        await self.db.refresh(agent_model)

        return AgentProfile.model_validate(agent_model)

    async def evaluate_transaction(
        self, request: AgentTransactionRequest
    ) -> AgentDecision:
        """Run policy checks in strict sequence and evaluate a transaction request.

        Evaluation order:
        1. Agent exists and is active
        2. Idempotency: same key not used before (or same key with same payload = cached result)
        3. Idempotency conflict: same key with DIFFERENT payload = DENY
        4. Amount does not exceed max_transaction_amount
        5. Currency is in allowed_currencies list
        6. Merchant is in allowed_merchants list (or empty = all allowed)
        7. Category (MCC) is in allowed_categories list (or empty = all allowed)
        8. Daily spending not exceeded (sum of approved transactions today in UTC)
        9. Velocity check: no more than 10 transactions per minute per agent
        10. Human approval required if amount > requires_human_approval_above

        Args:
            request: Agent transaction request to evaluate.

        Returns:
            AgentDecision: Final policy decision (APPROVE, DENY, or ESCALATE).
        """
        # Acquire a database write lock on the agent row before reading budget
        # state. Unlike an asyncio lock, this serializes workers and processes.
        lock = await self._get_agent_lock(request.agent_id)
        await self.db.execute(
            update(AgentProfileModel)
            .where(AgentProfileModel.agent_id == request.agent_id)
            .values(updated_at=AgentProfileModel.updated_at)
        )
        async with lock:
            now_utc = datetime.now(timezone.utc)
            violations: list[str] = []

            # Check 1: Agent exists and is active
            stmt = (
                select(AgentProfileModel)
                .where(AgentProfileModel.agent_id == request.agent_id)
                .with_for_update()
            )
            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()

            if agent is None:
                decision = AgentDecision(
                    decision=AgentDecisionEnum.DENY,
                    agent_id=request.agent_id,
                    transaction_id=None,
                    idempotency_key=request.idempotency_key,
                    amount=request.amount,
                    currency=request.currency,
                    violations=[f"AGENT_NOT_FOUND: Agent '{request.agent_id}' does not exist"],
                    risk_score=100.0,
                    requires_human_approval=False,
                    cached=False,
                    evaluated_at=now_utc,
                )
                await self._log_audit(
                    agent_id=request.agent_id,
                    event_type="TRANSACTION_DENIED_UNKNOWN_AGENT",
                    details={
                        "idempotency_key": request.idempotency_key,
                        "amount": str(request.amount),
                    },
                )
                await self.db.commit()
                return decision

            if agent.status != "ACTIVE":
                decision = AgentDecision(
                    decision=AgentDecisionEnum.DENY,
                    agent_id=request.agent_id,
                    transaction_id=None,
                    idempotency_key=request.idempotency_key,
                    amount=request.amount,
                    currency=request.currency,
                    violations=[
                        f"AGENT_INACTIVE: Agent '{request.agent_id}' status is {agent.status}"
                    ],
                    risk_score=100.0,
                    requires_human_approval=False,
                    cached=False,
                    evaluated_at=now_utc,
                )
                await self._log_audit(
                    agent_id=request.agent_id,
                    event_type="TRANSACTION_DENIED_INACTIVE_AGENT",
                    details={
                        "idempotency_key": request.idempotency_key,
                        "amount": str(request.amount),
                    },
                )
                await self.db.commit()
                return decision

            # Check 2 & 3: Idempotency validation
            current_payload_hash = self._compute_payload_hash(request)
            idemp_stmt = select(AgentTransactionModel).where(
                AgentTransactionModel.agent_id == request.agent_id,
                AgentTransactionModel.idempotency_key == request.idempotency_key,
            )
            idemp_result = await self.db.execute(idemp_stmt)
            existing_tx = idemp_result.scalar_one_or_none()

            if existing_tx is not None:
                # Same key and same payload: return cached decision
                if existing_tx.payload_hash == current_payload_hash:
                    return AgentDecision(
                        decision=AgentDecisionEnum(existing_tx.decision),
                        agent_id=existing_tx.agent_id,
                        transaction_id=existing_tx.id,
                        idempotency_key=existing_tx.idempotency_key,
                        amount=existing_tx.amount,
                        currency=existing_tx.currency,
                        violations=existing_tx.violations or [],
                        review_reasons=existing_tx.review_reasons or [],
                        risk_score=existing_tx.risk_score,
                        requires_human_approval=existing_tx.requires_human_approval,
                        cached=True,
                        evaluated_at=existing_tx.created_at,
                    )
                # Same key with DIFFERENT payload: immediate DENY
                conflict_msg = (
                    f"IDEMPOTENCY_CONFLICT: Idempotency key '{request.idempotency_key}' "
                    f"reused with differing payload"
                )
                await self._log_audit(
                    agent_id=request.agent_id,
                    event_type="IDEMPOTENCY_CONFLICT_DETECTED",
                    details={
                        "idempotency_key": request.idempotency_key,
                        "stored_hash": existing_tx.payload_hash,
                        "new_hash": current_payload_hash,
                    },
                )
                await self.db.commit()
                return AgentDecision(
                    decision=AgentDecisionEnum.DENY,
                    agent_id=request.agent_id,
                    transaction_id=None,
                    idempotency_key=request.idempotency_key,
                    amount=request.amount,
                    currency=request.currency,
                    violations=[conflict_msg],
                    risk_score=100.0,
                    requires_human_approval=False,
                    cached=False,
                    evaluated_at=now_utc,
                )

            # Edge case: Negative or zero transaction amount
            if request.amount <= 0:
                violations.append("INVALID_AMOUNT: Transaction amount must be greater than zero")

            # Edge case: Invalid MCC code format
            if request.category_mcc is not None:
                clean_mcc = request.category_mcc.strip()
                if not (clean_mcc.isdigit() and len(clean_mcc) == 4):
                    violations.append(
                        f"INVALID_MCC: Category MCC '{request.category_mcc}' must be a 4-digit numeric code"
                    )

            # Check 4: Amount does not exceed max_transaction_amount
            req_currency = request.currency.strip().upper()
            same_budget_currency = req_currency == agent.budget_currency
            review_reasons: list[str] = []
            if not same_budget_currency:
                violations.append(
                    f"CURRENCY_CONVERSION_UNAVAILABLE: Cannot enforce transaction and daily "
                    f"limits denominated in {agent.budget_currency} without a trusted exchange rate."
                )

            if same_budget_currency and request.amount > agent.max_transaction_amount:
                violations.append(
                    f"MAX_TRANSACTION_AMOUNT_EXCEEDED: Amount {request.amount} "
                    f"exceeds limit {agent.max_transaction_amount}"
                )

            # Check 5: Currency is in allowed_currencies list
            allowed_currs = [c.upper() for c in agent.allowed_currencies]
            if req_currency not in allowed_currs:
                violations.append(
                    f"CURRENCY_NOT_ALLOWED: Currency '{request.currency}' "
                    f"is not in allowed currencies {agent.allowed_currencies}"
                )

            # Check 6: Merchant is in allowed_merchants list (or empty = all allowed)
            if agent.allowed_merchants:
                target_merchant = request.merchant_id.strip()
                target_name = (request.merchant_name or "").strip()
                if (
                    target_merchant not in agent.allowed_merchants
                    and target_name not in agent.allowed_merchants
                ):
                    violations.append(
                        f"MERCHANT_NOT_ALLOWED: Merchant '{request.merchant_id}' "
                        f"is not in allowed merchants list"
                    )

            # Check 7: Category (MCC) is in allowed_categories list (or empty = all allowed)
            if agent.allowed_categories:
                target_mcc = (request.category_mcc or "").strip()
                if not target_mcc or target_mcc not in agent.allowed_categories:
                    violations.append(
                        f"CATEGORY_NOT_ALLOWED: Category MCC '{request.category_mcc}' "
                        f"is not in allowed categories list"
                    )

            # Check 8: Daily spending not exceeded (sum of approved transactions today in UTC)
            spending_data = await self.get_agent_spending(
                agent_id=request.agent_id, date=now_utc.date()
            )
            current_spent_today = spending_data["total_spent"]
            if same_budget_currency and (
                current_spent_today + request.amount > agent.daily_spending_limit
            ):
                violations.append(
                    f"DAILY_SPENDING_LIMIT_EXCEEDED: Requested {request.amount} "
                    f"exceeds remaining daily budget {spending_data['remaining_budget']} "
                    f"(spent today: {current_spent_today}, limit: {agent.daily_spending_limit})"
                )

            # Check 9: Velocity check: no more than 10 transactions per minute per agent
            one_min_ago = now_utc - timedelta(seconds=60)
            velocity_stmt = select(func.count(AgentTransactionModel.id)).where(
                AgentTransactionModel.agent_id == request.agent_id,
                AgentTransactionModel.created_at >= one_min_ago,
            )
            velocity_result = await self.db.execute(velocity_stmt)
            recent_velocity = velocity_result.scalar_one() or 0

            if recent_velocity >= 10:
                violations.append(
                    f"VELOCITY_LIMIT_EXCEEDED: Reached {recent_velocity} transactions "
                    f"in the last minute (maximum allowed: 10/min)"
                )

            # Check 10: Human approval required if amount > requires_human_approval_above
            human_approval_triggered = False
            if same_budget_currency and (
                agent.requires_human_approval_above is not None
                and request.amount > agent.requires_human_approval_above
            ):
                human_approval_triggered = True
            # Determine decision
            if violations:
                decision_enum = AgentDecisionEnum.DENY
            elif human_approval_triggered:
                decision_enum = AgentDecisionEnum.ESCALATE
            else:
                decision_enum = AgentDecisionEnum.APPROVE

            # Calculate risk score
            agent_profile = AgentProfile.model_validate(agent)
            risk_score = calculate_agent_risk(
                agent=agent_profile,
                transaction=request,
                recent_velocity=recent_velocity,
            )

            # Save decision to AgentTransaction table
            tx_id = str(uuid.uuid4())
            tx_record = AgentTransactionModel(
                id=tx_id,
                idempotency_key=request.idempotency_key,
                agent_id=request.agent_id,
                amount=request.amount,
                currency=request.currency.strip().upper(),
                merchant_id=request.merchant_id.strip(),
                merchant_name=request.merchant_name,
                category_mcc=request.category_mcc,
                payload_hash=current_payload_hash,
                decision=decision_enum.value,
                violations=violations,
                review_reasons=review_reasons,
                risk_score=risk_score,
                requires_human_approval=human_approval_triggered,
                metadata_json=request.metadata,
                created_at=now_utc,
            )
            self.db.add(tx_record)

            # Save to AuditLog
            await self._log_audit(
                agent_id=request.agent_id,
                event_type=f"TRANSACTION_{decision_enum.value}",
                details={
                    "transaction_id": tx_id,
                    "idempotency_key": request.idempotency_key,
                    "amount": str(request.amount),
                    "currency": request.currency,
                    "merchant_id": request.merchant_id,
                    "category_mcc": request.category_mcc,
                    "decision": decision_enum.value,
                    "violations": violations,
                    "review_reasons": review_reasons,
                    "risk_score": risk_score,
                    "requires_human_approval": human_approval_triggered,
                },
            )
            await self.db.commit()

            return AgentDecision(
                decision=decision_enum,
                agent_id=request.agent_id,
                transaction_id=tx_id,
                idempotency_key=request.idempotency_key,
                amount=request.amount,
                currency=request.currency,
                violations=violations,
                review_reasons=review_reasons,
                risk_score=risk_score,
                requires_human_approval=human_approval_triggered,
                cached=False,
                evaluated_at=now_utc,
            )

    async def get_agent_spending(
        self, agent_id: str, date: Optional[date] = None
    ) -> dict[str, Any]:
        """Aggregate total approved spending and remaining budget for a UTC day.

        Args:
            agent_id: Agent identifier.
            date: Target date (defaults to current UTC date).

        Returns:
            dict: Summary with total_spent, transaction_count, remaining_budget, daily_spending_limit.

        Raises:
            ValueError: If agent is not found.
        """
        # Fetch agent profile
        stmt = select(AgentProfileModel).where(AgentProfileModel.agent_id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found")

        target_date = date or datetime.now(timezone.utc).date()
        day_start = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

        # Aggregate approved transactions within UTC day
        agg_stmt = select(
            func.coalesce(func.sum(AgentTransactionModel.amount), Decimal("0")),
            func.count(AgentTransactionModel.id),
        ).where(
            AgentTransactionModel.agent_id == agent_id,
            AgentTransactionModel.currency == agent.budget_currency,
            AgentTransactionModel.decision.in_(
                [AgentDecisionEnum.APPROVE.value, AgentDecisionEnum.ESCALATE.value]
            ),
            AgentTransactionModel.created_at >= day_start,
            AgentTransactionModel.created_at <= day_end,
        )
        agg_result = await self.db.execute(agg_stmt)
        total_spent, tx_count = agg_result.one()

        total_spent = Decimal(str(total_spent))
        tx_count = int(tx_count)
        remaining = max(Decimal("0"), agent.daily_spending_limit - total_spent)

        return {
            "agent_id": agent_id,
            "date": target_date.isoformat(),
            "total_spent": total_spent,
            "transaction_count": tx_count,
            "daily_spending_limit": agent.daily_spending_limit,
            "budget_currency": agent.budget_currency,
            "remaining_budget": remaining,
        }

    async def update_agent_policy(
        self, agent_id: str, updates: dict[str, Any], caller_id: Optional[str] = None
    ) -> AgentProfile:
        """Update agent spending rules and policy configuration.

        Security rules enforced:
        - An agent is strictly prohibited from modifying its own spending limits
        - Only the authorized agent owner can perform policy updates

        Args:
            agent_id: Agent identifier to update.
            updates: Dictionary of policy changes.
            caller_id: Identifier of the entity requesting the update.

        Returns:
            AgentProfile: The updated profile.

        Raises:
            PermissionError: If caller is the agent itself or not the owner.
            ValueError: If agent is not found or policy limits are invalid.
        """
        # Security rule: Agent cannot modify its own spending limits
        if caller_id is None or not caller_id.strip():
            raise PermissionError("Caller identity is required to update agent policy")
        if caller_id.strip() == agent_id.strip():
            await self._log_audit(
                agent_id=agent_id,
                event_type="UNAUTHORIZED_POLICY_MODIFICATION_ATTEMPT",
                details={
                    "caller_id": caller_id,
                    "attempted_updates": list(updates.keys()),
                },
            )
            await self.db.commit()
            raise PermissionError(
                "Security violation: Agent is not allowed to modify its own spending limits"
            )

        if not self.db.in_transaction():
            if self.db.bind is not None and self.db.bind.dialect.name == "sqlite":
                await self.db.execute(text("BEGIN IMMEDIATE"))
        stmt = (
            select(AgentProfileModel)
            .where(AgentProfileModel.agent_id == agent_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Owner authorization check
        if caller_id.strip() != agent.owner_id.strip():
            raise PermissionError(
                f"Unauthorized: Caller '{caller_id}' is not the owner of agent '{agent_id}'"
            )

        # Validate updates
        if "max_transaction_amount" in updates:
            val = Decimal(str(updates["max_transaction_amount"]))
            if val <= 0:
                raise ValueError("max_transaction_amount must be greater than zero")
            agent.max_transaction_amount = val

        if "daily_spending_limit" in updates:
            val = Decimal(str(updates["daily_spending_limit"]))
            if val <= 0:
                raise ValueError("daily_spending_limit must be greater than zero")
            agent.daily_spending_limit = val

        if agent.daily_spending_limit < agent.max_transaction_amount:
            raise ValueError("daily_spending_limit cannot be less than max_transaction_amount")

        if "allowed_currencies" in updates:
            currs = updates["allowed_currencies"]
            if not currs:
                raise ValueError("allowed_currencies must include at least one currency")
            agent.allowed_currencies = [c.strip().upper() for c in currs]

        if "budget_currency" in updates:
            if updates["budget_currency"] is None:
                raise ValueError("budget_currency cannot be null")
            agent.budget_currency = updates["budget_currency"].strip().upper()
        if agent.budget_currency not in agent.allowed_currencies:
            raise ValueError("budget_currency must be included in allowed_currencies")

        if "allowed_merchants" in updates:
            agent.allowed_merchants = updates["allowed_merchants"]

        if "allowed_categories" in updates:
            agent.allowed_categories = updates["allowed_categories"]

        if "requires_human_approval_above" in updates:
            val = updates["requires_human_approval_above"]
            if val is not None and Decimal(str(val)) <= 0:
                raise ValueError("requires_human_approval_above must be greater than zero")
            agent.requires_human_approval_above = (
                Decimal(str(val)) if val is not None else None
            )
        if (
            agent.requires_human_approval_above is not None
            and agent.requires_human_approval_above > agent.max_transaction_amount
        ):
            raise ValueError(
                "requires_human_approval_above cannot exceed max_transaction_amount"
            )
        minor_units = get_currency_info(agent.budget_currency).get("minor_units", 2)
        policy_amounts = [
            agent.max_transaction_amount,
            agent.daily_spending_limit,
            agent.requires_human_approval_above,
        ]
        if any(
            value is not None
            and max(0, -value.as_tuple().exponent) > minor_units
            for value in policy_amounts
        ):
            raise ValueError(
                f"Policy amounts may use at most {minor_units} decimal places "
                f"for {agent.budget_currency}"
            )

        if "status" in updates:
            new_status = updates["status"]
            if new_status not in ["ACTIVE", "INACTIVE"]:
                raise ValueError("status must be ACTIVE or INACTIVE")
            agent.status = new_status

        if "name" in updates and updates["name"]:
            agent.name = updates["name"].strip()

        if "description" in updates:
            agent.description = updates["description"]

        agent.updated_at = datetime.now(timezone.utc)

        await self._log_audit(
            agent_id=agent_id,
            event_type="POLICY_UPDATED",
            details={
                "caller_id": caller_id or "system",
                "updated_keys": list(updates.keys()),
            },
        )
        await self.db.commit()
        await self.db.refresh(agent)

        return AgentProfile.model_validate(agent)

    async def deactivate_agent(
        self, agent_id: str, caller_id: Optional[str] = None
    ) -> bool:
        """Deactivate an agent, preventing all future transactions.

        Args:
            agent_id: Identifier of the agent to deactivate.

        Returns:
            bool: True if deactivated, False if agent was not found.
        """
        if not self.db.in_transaction():
            if self.db.bind is not None and self.db.bind.dialect.name == "sqlite":
                await self.db.execute(text("BEGIN IMMEDIATE"))
        stmt = (
            select(AgentProfileModel)
            .where(AgentProfileModel.agent_id == agent_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is None:
            return False
        if caller_id is None or caller_id.strip() != agent.owner_id.strip():
            raise PermissionError("Only the registered agent owner can deactivate it")

        agent.status = "INACTIVE"
        agent.updated_at = datetime.now(timezone.utc)

        await self._log_audit(
            agent_id=agent_id,
            event_type="AGENT_DEACTIVATED",
            details={"status": "INACTIVE"},
        )
        await self.db.commit()
        return True

    async def get_audit_trail(self, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve historical audit trail logs for an agent.

        Args:
            agent_id: Identifier of the agent.
            limit: Maximum number of audit records to return (default 50).

        Returns:
            list[dict]: Ordered list of audit log records.
        """
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.agent_id == agent_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": row.id,
                "agent_id": row.agent_id,
                "event_type": row.event_type,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    async def list_agents(self) -> list[AgentProfile]:
        """List all registered agent profiles.

        Returns:
            list[AgentProfile]: List of all agent profiles in the database.
        """
        stmt = select(AgentProfileModel).order_by(AgentProfileModel.created_at.desc())
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [AgentProfile.model_validate(row) for row in rows]
