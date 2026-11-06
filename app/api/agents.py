"""FastAPI router for Agent Commerce Guard endpoints."""

from datetime import date
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db as get_db_session
from app.models.agent import AgentProfileModel
from app.schemas.agent import (
    AgentDecision,
    AgentDetailResponse,
    AgentIntentEvaluationResponse,
    AgentIntentRequest,
    AgentPolicyUpdate,
    AgentProfile,
    AgentRegistration,
    AgentSpendingSummary,
    AgentTransactionRequest,
    AuditLogResponse,
)
from app.services.ai_intent import AIIntentClient
from app.services.agent_guard import AgentGuard
from app.security import principal_has_scope, require_scopes

router = APIRouter(prefix="/api/agents", tags=["Agent Commerce Guard"])


def get_agent_guard(db: AsyncSession = Depends(get_db_session)) -> AgentGuard:
    """Dependency provider for AgentGuard service instance.

    Args:
        db: Injected asynchronous database session.

    Returns:
        AgentGuard: Configured guard service instance.
    """
    return AgentGuard(db)


@router.post(
    "/register",
    response_model=AgentProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
async def register_agent(
    registration: AgentRegistration,
    guard: AgentGuard = Depends(get_agent_guard),
    principal: dict[str, Any] = Depends(require_scopes("sentinel:agents:manage")),
) -> AgentProfile:
    """Register a new autonomous AI agent with custom spending limits.

    Args:
        registration: Agent configuration including limits and currency allowlists.
        guard: Injected AgentGuard service.

    Returns:
        AgentProfile: Created agent profile record.
    """
    try:
        if (
            not principal.get("development_mode")
            and registration.owner_id != principal["sub"]
            and not principal_has_scope(principal, "sentinel:admin")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent owner_id must match the authenticated subject",
            )
        return await guard.register_agent(registration)
    except HTTPException:
        raise
    except ValueError as exc:
        err_msg = str(exc)
        if "already registered" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        ) from exc


@router.post(
    "/evaluate",
    response_model=AgentDecision,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a transaction request",
)
async def evaluate_transaction(
    request: AgentTransactionRequest,
    guard: AgentGuard = Depends(get_agent_guard),
    _principal: dict[str, Any] = Depends(require_scopes("sentinel:agents:evaluate")),
) -> AgentDecision:
    """Evaluate an agent transaction against merchant policies and limits.

    Runs sequential policy verification:
    1. Active status
    2. Idempotency and payload collision checks
    3. Transaction size limit
    4. Currency allowlist
    5. Merchant allowlist
    6. Category MCC allowlist
    7. Daily aggregate spending limit (UTC)
    8. Transaction velocity check
    9. Human escalation threshold

    Args:
        request: Transaction request details.
        guard: Injected AgentGuard service.

    Returns:
        AgentDecision: APPROVE, DENY, or ESCALATE decision with violations.
    """
    return await guard.evaluate_transaction(request)


@router.post(
    "/interpret-and-evaluate",
    response_model=AgentIntentEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract a natural-language purchase and evaluate agent policy",
)
async def interpret_and_evaluate(
    request: AgentIntentRequest,
    guard: AgentGuard = Depends(get_agent_guard),
    _principal: dict[str, Any] = Depends(
        require_scopes("sentinel:agents:evaluate")
    ),
) -> AgentIntentEvaluationResponse:
    """Use a configured AI model for extraction, then apply deterministic policy."""
    extracted = await AIIntentClient().extract(request.instruction)
    try:
        transaction = AgentTransactionRequest(
            idempotency_key=request.idempotency_key,
            agent_id=request.agent_id,
            merchant_id=request.merchant_id,
            amount=extracted.amount,
            currency=extracted.currency,
            merchant_name=extracted.merchant_name,
            category_mcc=extracted.category_mcc,
            description=extracted.description,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned purchase fields that failed validation",
        ) from exc
    decision = await guard.evaluate_transaction(transaction)
    return AgentIntentEvaluationResponse(
        ai_model=settings.AI_MODEL,
        extracted_intent=extracted,
        decision=decision,
    )


@router.get(
    "",
    response_model=list[AgentProfile],
    status_code=status.HTTP_200_OK,
    summary="List all registered agents",
)
async def list_agents(
    guard: AgentGuard = Depends(get_agent_guard),
) -> list[AgentProfile]:
    """Retrieve all registered agent profiles.

    Args:
        guard: Injected AgentGuard service.

    Returns:
        list[AgentProfile]: All configured agents.
    """
    return await guard.list_agents()


@router.get(
    "/{agent_id}",
    response_model=AgentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get agent profile and current spending",
)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
    guard: AgentGuard = Depends(get_agent_guard),
) -> AgentDetailResponse:
    """Retrieve an agent profile together with current day spending summary.

    Args:
        agent_id: Target agent identifier.
        db: Injected database session.
        guard: Injected AgentGuard service.

    Returns:
        AgentDetailResponse: Combined profile and spending metrics.
    """
    stmt = select(AgentProfileModel).where(AgentProfileModel.agent_id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    profile = AgentProfile.model_validate(agent)
    spending_data = await guard.get_agent_spending(agent_id)
    spending_summary = AgentSpendingSummary(**spending_data)

    return AgentDetailResponse(agent=profile, spending=spending_summary)


@router.put(
    "/{agent_id}/policy",
    response_model=AgentProfile,
    status_code=status.HTTP_200_OK,
    summary="Update agent policy (only owner can do this)",
)
async def update_agent_policy(
    agent_id: str,
    updates: AgentPolicyUpdate,
    guard: AgentGuard = Depends(get_agent_guard),
    principal: dict[str, Any] = Depends(require_scopes("sentinel:agents:manage")),
) -> AgentProfile:
    """Update spending limits and allowlists for an existing agent.

    CRITICAL SECURITY ENFORCEMENT:
    An agent is strictly forbidden from modifying its own spending limits.
    Only the authorized merchant or owner may perform policy updates.

    Args:
        agent_id: Target agent identifier.
        updates: Policy updates to apply.
        x_caller_id: Caller identity passed via header.
        guard: Injected AgentGuard service.

    Returns:
        AgentProfile: Updated agent profile.
    """
    owner_id = str(principal["sub"])
    if owner_id.strip() == agent_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security violation: Agent is not allowed to modify its own spending limits",
        )

    try:
        update_dict = updates.model_dump(exclude_unset=True)
        return await guard.update_agent_policy(
            agent_id=agent_id, updates=update_dict, caller_id=owner_id
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        err_msg = str(exc)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        ) from exc


@router.delete(
    "/{agent_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Deactivate agent",
)
async def deactivate_agent(
    agent_id: str,
    guard: AgentGuard = Depends(get_agent_guard),
    principal: dict[str, Any] = Depends(require_scopes("sentinel:agents:manage")),
) -> dict[str, Any]:
    """Deactivate an agent, preventing any subsequent transaction evaluations.

    Args:
        agent_id: Target agent identifier.
        guard: Injected AgentGuard service.

    Returns:
        dict: Confirmation payload indicating deactivation.
    """
    try:
        success = await guard.deactivate_agent(
            agent_id, caller_id=str(principal["sub"])
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )
    return {"status": "deactivated", "agent_id": agent_id}


@router.get(
    "/{agent_id}/audit",
    response_model=list[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get audit trail",
)
async def get_audit_trail(
    agent_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    guard: AgentGuard = Depends(get_agent_guard),
) -> list[AuditLogResponse]:
    """Retrieve the immutable audit trail logs for an agent.

    Args:
        agent_id: Target agent identifier.
        limit: Maximum number of records to return.
        db: Injected database session.
        guard: Injected AgentGuard service.

    Returns:
        list[AuditLogResponse]: Audit log entries ordered newest first.
    """
    stmt = select(AgentProfileModel).where(AgentProfileModel.agent_id == agent_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    records = await guard.get_audit_trail(agent_id, limit=limit)
    return [AuditLogResponse.model_validate(rec) for rec in records]


@router.get(
    "/{agent_id}/spending",
    response_model=AgentSpendingSummary,
    status_code=status.HTTP_200_OK,
    summary="Get daily spending summary",
)
async def get_spending(
    agent_id: str,
    target_date: Optional[date] = Query(None, alias="date"),
    guard: AgentGuard = Depends(get_agent_guard),
) -> AgentSpendingSummary:
    """Retrieve aggregated spending metrics for an agent on a specific UTC day.

    Args:
        agent_id: Target agent identifier.
        target_date: Target calendar date (defaults to UTC today).
        guard: Injected AgentGuard service.

    Returns:
        AgentSpendingSummary: Aggregated spent amount and remaining budget.
    """
    try:
        data = await guard.get_agent_spending(agent_id=agent_id, date=target_date)
        return AgentSpendingSummary(**data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
