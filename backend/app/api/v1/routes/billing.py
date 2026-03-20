"""Stripe billing routes -- checkout, portal, webhooks."""

from __future__ import annotations

import structlog
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import get_settings
from app.models.organization import Organization
from app.models.subscription import Subscription

logger = structlog.get_logger()
router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_LIMITS = {
    "free": {"max_projects": 1, "max_agents": 50, "price": 0},
    "starter": {"max_projects": 3, "max_agents": 50, "price": 199},
    "growth": {"max_projects": 10, "max_agents": 500, "price": 999},
    "enterprise": {"max_projects": 100, "max_agents": 10000, "price": 4999},
}


def _get_stripe():
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Billing not configured")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@router.get("/subscription")
async def get_subscription(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current org subscription details."""
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == user.org_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {
            "plan": "free",
            "status": "active",
            "max_projects": 1,
            "max_agents": 50,
            "monthly_price_eur": 0,
            "cancel_at_period_end": False,
        }
    return {
        "plan": sub.plan,
        "status": sub.status,
        "max_projects": sub.max_projects,
        "max_agents": sub.max_agents,
        "monthly_price_eur": sub.monthly_price_eur,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "stripe_customer_id": sub.stripe_customer_id,
    }


@router.post("/checkout")
async def create_checkout(
    plan: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for plan upgrade."""
    s = _get_stripe()
    settings = get_settings()

    if plan not in ("starter", "growth", "enterprise"):
        raise HTTPException(400, f"Invalid plan: {plan}")

    price_map = {
        "starter": settings.STRIPE_STARTER_PRICE_ID,
        "growth": settings.STRIPE_GROWTH_PRICE_ID,
        "enterprise": settings.STRIPE_ENTERPRISE_PRICE_ID,
    }
    price_id = price_map.get(plan)
    if not price_id:
        raise HTTPException(503, f"Price not configured for plan: {plan}")

    # Find or create Stripe customer
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == user.org_id)
    )
    sub = result.scalar_one_or_none()
    customer_id = sub.stripe_customer_id if sub else None

    if not customer_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.org_id)
        )
        org = org_result.scalar_one()
        customer = s.Customer.create(
            email=user.email,
            name=org.name,
            metadata={"org_id": str(user.org_id)},
        )
        customer_id = customer.id

    session = s.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.APP_URL}/settings?billing=success",
        cancel_url=f"{settings.APP_URL}/settings?billing=canceled",
        metadata={"org_id": str(user.org_id), "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for self-service billing management."""
    s = _get_stripe()
    settings = get_settings()

    result = await db.execute(
        select(Subscription).where(Subscription.org_id == user.org_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(400, "No active subscription")

    session = s.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.APP_URL}/settings",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events for subscription lifecycle."""
    settings = get_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        await logger.awarn("stripe_webhook_invalid", error=str(e))
        raise HTTPException(400, "Invalid webhook") from e

    event_type = event["type"]
    data = event["data"]["object"]

    await logger.ainfo("stripe_webhook", type=event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data)
    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        await _handle_subscription_change(db, data)

    return {"received": True}


async def _handle_checkout_completed(db: AsyncSession, session_data: dict):
    """Provision subscription after successful checkout."""
    org_id = session_data.get("metadata", {}).get("org_id")
    plan = session_data.get("metadata", {}).get("plan", "starter")
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    if not org_id or not customer_id:
        await logger.awarn("stripe_checkout_missing_metadata", data=session_data)
        return

    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])

    result = await db.execute(
        select(Subscription).where(Subscription.org_id == org_id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        sub.stripe_customer_id = customer_id
        sub.stripe_subscription_id = subscription_id
        sub.plan = plan
        sub.status = "active"
        sub.max_projects = limits["max_projects"]
        sub.max_agents = limits["max_agents"]
        sub.monthly_price_eur = limits["price"]
    else:
        sub = Subscription(
            org_id=org_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            status="active",
            max_projects=limits["max_projects"],
            max_agents=limits["max_agents"],
            monthly_price_eur=limits["price"],
        )
        db.add(sub)

    # Update org plan
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if org:
        org.plan = plan

    await db.commit()
    await logger.ainfo("subscription_provisioned", org_id=org_id, plan=plan)


async def _handle_subscription_change(db: AsyncSession, sub_data: dict):
    """Update subscription status on change or cancellation."""
    from datetime import datetime, timezone

    customer_id = sub_data.get("customer")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    sub.status = sub_data.get("status", sub.status)
    sub.cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

    period_end = sub_data.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    period_start = sub_data.get("current_period_start")
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)

    if sub_data.get("status") == "canceled":
        sub.plan = "free"
        sub.max_projects = 1
        sub.max_agents = 50
        sub.monthly_price_eur = 0

        org_result = await db.execute(
            select(Organization).where(Organization.id == sub.org_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = "free"

    await db.commit()
    await logger.ainfo(
        "subscription_updated",
        customer=customer_id,
        status=sub.status,
        plan=sub.plan,
    )
