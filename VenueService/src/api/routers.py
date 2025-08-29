from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .models import (
    AvailabilityResponse,
    ReleaseSeatsRequest,
    SeatAllocationRequest,
    SeatHoldRequest,
    SeatMapUpsert,
    SeatPublic,
    SeatTypeConfig,
    VenueCreate,
    VenuePublic,
    VenueUpdate,
    STORE,
)
from .security import Principal, get_current_principal, require_roles


router = APIRouter()


# Health tag router
health_router = APIRouter(tags=["health"])


@health_router.get("/", summary="Health check", description="Simple health check endpoint.")
# PUBLIC_INTERFACE
def health_check():
    """Return a simple response indicating the service is healthy."""
    return {"message": "Healthy"}


# Venues router
venues_router = APIRouter(prefix="/venues", tags=["venues"])


@venues_router.post(
    "",
    summary="Create venue",
    description="Create a new venue (organizer/admin).",
    response_model=VenuePublic,
    status_code=201,
)
# PUBLIC_INTERFACE
def create_venue(payload: VenueCreate, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Create a new venue."""
    return STORE.create_venue(payload)


@venues_router.get("", summary="List venues", description="List all venues.", response_model=List[VenuePublic])
# PUBLIC_INTERFACE
def list_venues(_: Principal = Depends(get_current_principal)):
    """List venues."""
    return STORE.list_venues()


@venues_router.get("/{venue_id}", summary="Get venue", description="Get venue by ID.", response_model=VenuePublic)
# PUBLIC_INTERFACE
def get_venue(venue_id: str, _: Principal = Depends(get_current_principal)):
    """Get a single venue by id."""
    v = STORE.get_venue(venue_id)
    if not v:
        raise HTTPException(status_code=404, detail="Venue not found")
    return v


@venues_router.put("/{venue_id}", summary="Update venue", description="Update a venue.", response_model=VenuePublic)
# PUBLIC_INTERFACE
def update_venue(venue_id: str, payload: VenueUpdate, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Update venue fields."""
    v = STORE.update_venue(venue_id, payload)
    if not v:
        raise HTTPException(status_code=404, detail="Venue not found")
    return v


@venues_router.delete(
    "/{venue_id}",
    summary="Delete venue",
    description="Delete a venue and its seat map.",
    responses={204: {"description": "Deleted"}},
    status_code=204,
)
# PUBLIC_INTERFACE
def delete_venue(venue_id: str, principal: Principal = Depends(require_roles("admin"))):
    """Delete a venue."""
    ok = STORE.delete_venue(venue_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Venue not found")
    return None


# Seats and seat types
seats_router = APIRouter(prefix="/venues/{venue_id}/seats", tags=["seats"])


@seats_router.put(
    "/map",
    summary="Upsert seat map",
    description="Create or replace a venue's seat map and dimensions.",
    responses={200: {"description": "Seat map upserted"}},
)
# PUBLIC_INTERFACE
def upsert_seat_map(venue_id: str, seat_map: SeatMapUpsert, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Create or replace the seat map for a venue."""
    try:
        width, height, seats = STORE.upsert_seat_map(venue_id, seat_map)
        return {"width": width, "height": height, "seats": seats}
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


@seats_router.get(
    "/map",
    summary="Get seat map",
    description="Retrieve the venue seat grid and seats.",
)
# PUBLIC_INTERFACE
def get_seat_map(venue_id: str, _: Principal = Depends(get_current_principal)):
    """Return seat map."""
    try:
        width, height, seats = STORE.get_seat_map(venue_id)
        return {"width": width, "height": height, "seats": seats}
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


@seats_router.put(
    "/types",
    summary="Set seat types",
    description="Replace seat type configuration for a venue.",
    response_model=List[SeatTypeConfig],
)
# PUBLIC_INTERFACE
def set_seat_types(venue_id: str, types: List[SeatTypeConfig], principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Set seat type configurations."""
    try:
        return STORE.set_seat_types(venue_id, types)
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


@seats_router.get(
    "/types",
    summary="Get seat types",
    description="Retrieve seat type configuration for a venue.",
    response_model=List[SeatTypeConfig],
)
# PUBLIC_INTERFACE
def get_seat_types(venue_id: str, _: Principal = Depends(get_current_principal)):
    """Get seat type configurations."""
    try:
        return STORE.get_seat_types(venue_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


# Availability and allocation
availability_router = APIRouter(prefix="/venues/{venue_id}/availability", tags=["availability"])


@availability_router.get("", summary="Get availability", description="Get current availability snapshot.", response_model=AvailabilityResponse)
# PUBLIC_INTERFACE
def get_availability(venue_id: str, _: Principal = Depends(get_current_principal)):
    """Availability snapshot for a venue."""
    try:
        return STORE.get_availability(venue_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


allocation_router = APIRouter(prefix="/venues/{venue_id}/allocation", tags=["allocation"])


@allocation_router.post(
    "/hold",
    summary="Hold seats",
    description="Temporarily hold seats for a short TTL to avoid conflicts during checkout.",
    response_model=List[SeatPublic],
)
# PUBLIC_INTERFACE
def hold_seats(venue_id: str, req: SeatHoldRequest, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Hold seats to prevent race conditions while booking."""
    try:
        return STORE.hold_seats(venue_id, req)
    except KeyError as e:
        code = str(e).strip('"')
        if code.startswith("seat_not_found") or code == "venue_not_found":
            raise HTTPException(status_code=404, detail=code)
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@allocation_router.post(
    "/allocate",
    summary="Allocate (confirm) seats",
    description="Confirm seats (transition to allocated).",
    response_model=List[SeatPublic],
)
# PUBLIC_INTERFACE
def allocate_seats(venue_id: str, req: SeatAllocationRequest, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Confirm seats."""
    try:
        return STORE.allocate_seats(venue_id, req)
    except KeyError as e:
        code = str(e).strip('"')
        if code.startswith("seat_not_found") or code == "venue_not_found":
            raise HTTPException(status_code=404, detail=code)
        raise
    except ValueError as e:
        # hold expired, or unavailable
        raise HTTPException(status_code=409, detail=str(e))


@allocation_router.post(
    "/release",
    summary="Release held seats",
    description="Release held seats back to available.",
    response_model=List[SeatPublic],
)
# PUBLIC_INTERFACE
def release_seats(venue_id: str, req: ReleaseSeatsRequest, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Release held seats."""
    try:
        return STORE.release_seats(venue_id, req)
    except KeyError as e:
        code = str(e).strip('"')
        if code.startswith("seat_not_found") or code == "venue_not_found":
            raise HTTPException(status_code=404, detail=code)
        raise


# Analytics
analytics_router = APIRouter(prefix="/venues/{venue_id}/analytics", tags=["analytics"])


@analytics_router.get(
    "",
    summary="Venue analytics",
    description="Basic analytics for occupancy and status distribution.",
)
# PUBLIC_INTERFACE
def venue_analytics(venue_id: str, principal: Principal = Depends(require_roles("organizer", "admin"))):
    """Return analytics for a venue."""
    try:
        return STORE.analytics(venue_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Venue not found")


# Simple WebSocket for real-time availability broadcast (no broker, single-instance only)
class AvailabilityMessage(BaseModel):
    """Message for availability updates."""

    type: str = Field("availability", description="Message type identifier")
    payload: AvailabilityResponse


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, venue_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(venue_id, []).append(websocket)

    def disconnect(self, venue_id: str, websocket: WebSocket):
        arr = self.active_connections.get(venue_id, [])
        if websocket in arr:
            arr.remove(websocket)
        if not arr and venue_id in self.active_connections:
            self.active_connections.pop(venue_id, None)

    async def broadcast(self, venue_id: str, message: dict):
        for ws in self.active_connections.get(venue_id, []):
            await ws.send_json(message)


manager = ConnectionManager()


@availability_router.websocket(
    "/ws",
)
# PUBLIC_INTERFACE
async def availability_ws(websocket: WebSocket, venue_id: str):
    """
    WebSocket endpoint for real-time availability updates per venue.

    Usage:
    - Connect: ws://<host>/venues/{venue_id}/availability/ws
    - On connect, server may send current snapshot.
    - Subsequent updates can be broadcasted by server-side actions (in this stub, not automatically triggered).
    """
    await manager.connect(venue_id, websocket)
    try:
        # Send initial snapshot if venue exists
        try:
            snapshot = STORE.get_availability(venue_id)
            await websocket.send_json(AvailabilityMessage(payload=snapshot).model_dump())
        except KeyError:
            await websocket.send_json({"type": "error", "message": "venue_not_found"})
        # Keep alive and echo pings
        while True:
            _ = await websocket.receive_text()
            # No-op: in a real system we might treat messages as subscriptions or pings
            try:
                snapshot = STORE.get_availability(venue_id)
                await websocket.send_json(AvailabilityMessage(payload=snapshot).model_dump())
            except KeyError:
                await websocket.send_json({"type": "error", "message": "venue_not_found"})
    except WebSocketDisconnect:
        manager.disconnect(venue_id, websocket)
