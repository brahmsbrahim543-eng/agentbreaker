"""WebSocket routes -- live events and playground streaming."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.redis import get_redis_pool
from app.core.security import verify_token
from app.models.user import User

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
):
    """Live event stream for the authenticated user's organization.

    Subscribes to Redis pub/sub channel f"events:{org_id}" and forwards
    all messages to the WebSocket client.
    """
    # Authenticate via query param token
    try:
        payload = verify_token(token)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub")
    org_id = payload.get("org")
    if not user_id or not org_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Verify user exists
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return

    await websocket.accept()

    # Subscribe to Redis channel
    try:
        redis = get_redis_pool()
    except RuntimeError:
        await websocket.send_json({"type": "error", "message": "Redis unavailable"})
        await websocket.close(code=4500, reason="Redis unavailable")
        return

    pubsub = redis.pubsub()
    channel = f"events:{org_id}"
    await pubsub.subscribe(channel)

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "message": "Subscribed to live events",
        })

        # Forward Redis messages to WebSocket
        while True:
            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                timeout=30.0,
            )
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    await websocket.send_text(data)
                elif isinstance(data, bytes):
                    await websocket.send_text(data.decode("utf-8"))
            else:
                # Send keepalive ping every ~30s when no messages
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        # Send keepalive and continue
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            pass
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.websocket("/ws/playground/{session_id}")
async def ws_playground(
    websocket: WebSocket,
    session_id: str,
):
    """Playground simulation event stream.

    Subscribes to Redis channel f"playground:{session_id}" and forwards
    simulation events to the WebSocket client.
    """
    await websocket.accept()

    try:
        redis = get_redis_pool()
    except RuntimeError:
        await websocket.send_json({"type": "error", "message": "Redis unavailable"})
        await websocket.close(code=4500, reason="Redis unavailable")
        return

    pubsub = redis.pubsub()
    channel = f"playground:{session_id}"
    await pubsub.subscribe(channel)

    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Subscribed to playground events",
        })

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                # No messages for 60s, simulation likely done
                await websocket.send_json({"type": "timeout", "message": "No events received"})
                break

            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    parsed = json.loads(data)
                    await websocket.send_json(parsed)

                    # Close if simulation is complete or killed
                    if parsed.get("type") in ("complete", "kill", "error"):
                        break
                elif isinstance(data, bytes):
                    parsed = json.loads(data.decode("utf-8"))
                    await websocket.send_json(parsed)
                    if parsed.get("type") in ("complete", "kill", "error"):
                        break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
