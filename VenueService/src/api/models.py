from __future__ import annotations

import enum
import time
import uuid
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, HttpUrl, field_validator


# Domain enums and constants
class SeatStatus(str, enum.Enum):
    available = "available"
    held = "held"
    allocated = "allocated"
    blocked = "blocked"


class SeatType(str, enum.Enum):
    standard = "standard"
    premium = "premium"
    vip = "vip"
    accessible = "accessible"
    custom = "custom"


# Pydantic models (DTOs)

# PUBLIC_INTERFACE
class VenueCreate(BaseModel):
    """Create a new venue with basic details, optional images, and optional default seat type."""

    name: str = Field(..., description="Venue name")
    address: str = Field(..., description="Venue address")
    city: str = Field(..., description="City")
    country: str = Field(..., description="Country")
    capacity: int = Field(..., ge=0, description="Total capacity (optional; can be computed from seats)")
    default_seat_type: SeatType = Field(
        SeatType.standard, description="Default seat type for this venue"
    )
    images: List[HttpUrl] = Field(default_factory=list, description="Optional image URLs")


# PUBLIC_INTERFACE
class VenueUpdate(BaseModel):
    """Update mutable venue fields."""

    name: Optional[str] = Field(None, description="Venue name")
    address: Optional[str] = Field(None, description="Venue address")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field(None, description="Country")
    capacity: Optional[int] = Field(None, ge=0, description="Capacity override")
    default_seat_type: Optional[SeatType] = Field(None, description="Default seat type")
    images: Optional[List[HttpUrl]] = Field(None, description="Image URLs")


# PUBLIC_INTERFACE
class VenuePublic(BaseModel):
    """Public representation of a venue."""

    id: str = Field(..., description="Venue ID")
    name: str
    address: str
    city: str
    country: str
    capacity: int
    default_seat_type: SeatType
    images: List[HttpUrl]


# Seat configuration

# PUBLIC_INTERFACE
class SeatDefinition(BaseModel):
    """Definition of a seat with coordinates in a map."""

    label: str = Field(..., description="Seat label, e.g., A-1")
    row: int = Field(..., ge=0, description="Row index (0-based)")
    col: int = Field(..., ge=0, description="Column index (0-based)")
    section: str = Field("main", description="Section within the venue")
    type: SeatType = Field(SeatType.standard, description="Seat type")
    price_modifier: float = Field(1.0, ge=0.0, description="Price multiplier for this seat")
    status: SeatStatus = Field(SeatStatus.available, description="Seat status")

    @field_validator("label")
    @classmethod
    def normalize_label(cls, v: str) -> str:
        return v.strip()


# PUBLIC_INTERFACE
class SeatTypeConfig(BaseModel):
    """Seat type configuration for a venue, defines defaults per type."""

    type: SeatType = Field(..., description="Seat type")
    display_name: str = Field(..., description="Display name for the seat type")
    color: str = Field("#4b5563", description="Hex color for seat rendering")
    base_price: float = Field(0.0, ge=0.0, description="Base price for this seat type")


# PUBLIC_INTERFACE
class SeatMapUpsert(BaseModel):
    """Seat map upsert payload for a venue."""

    width: int = Field(..., ge=1, description="Number of columns")
    height: int = Field(..., ge=1, description="Number of rows")
    seats: List[SeatDefinition] = Field(default_factory=list, description="List of seats")


# PUBLIC_INTERFACE
class SeatPublic(BaseModel):
    """Public seat representation."""

    label: str
    row: int
    col: int
    section: str
    type: SeatType
    status: SeatStatus
    price_modifier: float


# PUBLIC_INTERFACE
class SeatHoldRequest(BaseModel):
    """Request to hold one or more seats for a short time window."""

    seat_labels: List[str] = Field(..., description="Seat labels to hold")
    ttl_seconds: int = Field(120, ge=10, le=900, description="Time to live (seconds) for holds")
    reference: Optional[str] = Field(None, description="External reference (e.g., booking attempt id)")


# PUBLIC_INTERFACE
class SeatAllocationRequest(BaseModel):
    """Allocate seats (confirm) previously held or available."""

    seat_labels: List[str] = Field(..., description="Seat labels to allocate")
    order_id: str = Field(..., description="External order or booking id")


# PUBLIC_INTERFACE
class ReleaseSeatsRequest(BaseModel):
    """Release held seats back to available status."""

    seat_labels: List[str] = Field(..., description="Seat labels to release")


# PUBLIC_INTERFACE
class AvailabilityResponse(BaseModel):
    """Availability snapshot for a venue."""

    total: int
    available: int
    held: int
    allocated: int
    blocked: int
    timestamp: float = Field(..., description="Epoch seconds when the snapshot was taken")


# PUBLIC_INTERFACE
class AnalyticsResponse(BaseModel):
    """Basic analytics for a venue."""

    venue_id: str
    total_seats: int
    available: int
    held: int
    allocated: int
    blocked: int
    occupancy_rate: float = Field(..., description="Allocated / Total")
    held_rate: float = Field(..., description="Held / Total")


# In-memory repository (stub DB). Thread-safety is intentionally minimal for demo purposes.
class _SeatRecord(SeatDefinition):
    """
    Internal seat record with hold metadata.
    """

    hold_until: Optional[float] = None  # epoch seconds
    hold_ref: Optional[str] = None
    order_id: Optional[str] = None


class _VenueRecord(BaseModel):
    id: str
    data: VenuePublic
    width: int = 0
    height: int = 0
    seats: Dict[str, _SeatRecord] = {}
    types: Dict[SeatType, SeatTypeConfig] = {}


class InMemoryVenueStore:
    """
    Very simple in-memory store for venues, seats, types, and allocation state.
    For production, replace with a database and proper locking/transactions.
    """

    def __init__(self) -> None:
        self._venues: Dict[str, _VenueRecord] = {}

    # PUBLIC_INTERFACE
    def create_venue(self, payload: VenueCreate) -> VenuePublic:
        """Create a new venue with a unique ID."""
        venue_id = str(uuid.uuid4())
        vp = VenuePublic(
            id=venue_id,
            name=payload.name,
            address=payload.address,
            city=payload.city,
            country=payload.country,
            capacity=payload.capacity,
            default_seat_type=payload.default_seat_type,
            images=payload.images,
        )
        rec = _VenueRecord(id=venue_id, data=vp, width=0, height=0, seats={}, types={})
        # provide some default seat types
        rec.types[SeatType.standard] = SeatTypeConfig(type=SeatType.standard, display_name="Standard", color="#4b5563", base_price=0.0)
        rec.types[SeatType.premium] = SeatTypeConfig(type=SeatType.premium, display_name="Premium", color="#2563eb", base_price=0.0)
        rec.types[SeatType.vip] = SeatTypeConfig(type=SeatType.vip, display_name="VIP", color="#f59e0b", base_price=0.0)
        rec.types[SeatType.accessible] = SeatTypeConfig(type=SeatType.accessible, display_name="Accessible", color="#10b981", base_price=0.0)
        self._venues[venue_id] = rec
        return vp

    # PUBLIC_INTERFACE
    def list_venues(self) -> List[VenuePublic]:
        """List all venues."""
        return [v.data for v in self._venues.values()]

    # PUBLIC_INTERFACE
    def get_venue(self, venue_id: str) -> Optional[VenuePublic]:
        """Get a venue by id."""
        rec = self._venues.get(venue_id)
        return rec.data if rec else None

    # PUBLIC_INTERFACE
    def update_venue(self, venue_id: str, payload: VenueUpdate) -> Optional[VenuePublic]:
        """Update an existing venue."""
        rec = self._venues.get(venue_id)
        if not rec:
            return None
        data = rec.data.model_copy(deep=True)
        update_data = payload.model_dump(exclude_none=True)
        for k, v in update_data.items():
            setattr(data, k, v)
        rec.data = data
        self._venues[venue_id] = rec
        return data

    # PUBLIC_INTERFACE
    def delete_venue(self, venue_id: str) -> bool:
        """Delete a venue and its seats."""
        return self._venues.pop(venue_id, None) is not None

    # Seat map and types

    # PUBLIC_INTERFACE
    def upsert_seat_map(self, venue_id: str, seat_map: SeatMapUpsert) -> Tuple[int, int, List[SeatPublic]]:
        """Create or replace seat map for a venue."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        rec.width = seat_map.width
        rec.height = seat_map.height
        new_seats: Dict[str, _SeatRecord] = {}
        for s in seat_map.seats:
            label = s.label
            status = s.status
            new_seats[label] = _SeatRecord(**s.model_dump(), status=status)
        rec.seats = new_seats
        # capacity: if not explicitly set, compute
        if rec.data.capacity == 0:
            rec.data.capacity = len(new_seats)
        return rec.width, rec.height, [SeatPublic(**x.model_dump()) for x in rec.seats.values()]

    # PUBLIC_INTERFACE
    def get_seat_map(self, venue_id: str) -> Tuple[int, int, List[SeatPublic]]:
        """Get the seat grid and seats for a venue."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        return rec.width, rec.height, [SeatPublic(**x.model_dump()) for x in rec.seats.values()]

    # PUBLIC_INTERFACE
    def set_seat_types(self, venue_id: str, types: List[SeatTypeConfig]) -> List[SeatTypeConfig]:
        """Replace seat type configurations."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        rec.types = {t.type: t for t in types}
        return list(rec.types.values())

    # PUBLIC_INTERFACE
    def get_seat_types(self, venue_id: str) -> List[SeatTypeConfig]:
        """Get seat type configurations."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        return list(rec.types.values())

    # Availability and allocation

    def _purge_expired_holds(self, rec: _VenueRecord) -> None:
        now = time.time()
        for seat in rec.seats.values():
            if seat.status == SeatStatus.held and seat.hold_until and seat.hold_until <= now:
                seat.status = SeatStatus.available
                seat.hold_until = None
                seat.hold_ref = None

    # PUBLIC_INTERFACE
    def get_availability(self, venue_id: str) -> AvailabilityResponse:
        """Compute current availability for a venue."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        self._purge_expired_holds(rec)
        counts = {s: 0 for s in SeatStatus}
        for seat in rec.seats.values():
            counts[seat.status] += 1
        snapshot = AvailabilityResponse(
            total=len(rec.seats),
            available=counts[SeatStatus.available],
            held=counts[SeatStatus.held],
            allocated=counts[SeatStatus.allocated],
            blocked=counts[SeatStatus.blocked],
            timestamp=time.time(),
        )
        return snapshot

    # PUBLIC_INTERFACE
    def hold_seats(self, venue_id: str, req: SeatHoldRequest) -> List[SeatPublic]:
        """Hold seats temporarily."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        self._purge_expired_holds(rec)
        now = time.time()
        hold_until = now + req.ttl_seconds
        updated: List[SeatPublic] = []
        for label in req.seat_labels:
            seat = rec.seats.get(label)
            if not seat:
                raise KeyError(f"seat_not_found:{label}")
            if seat.status not in (SeatStatus.available, SeatStatus.held):
                raise ValueError(f"seat_unavailable:{label}")
            # If already held by someone else and not expired, reject
            if seat.status == SeatStatus.held and seat.hold_until and seat.hold_until > now and seat.hold_ref != req.reference:
                raise ValueError(f"seat_already_held:{label}")
            seat.status = SeatStatus.held
            seat.hold_until = hold_until
            seat.hold_ref = req.reference or str(uuid.uuid4())
            updated.append(SeatPublic(**seat.model_dump()))
        return updated

    # PUBLIC_INTERFACE
    def allocate_seats(self, venue_id: str, req: SeatAllocationRequest) -> List[SeatPublic]:
        """Allocate seats, transitioning from available/held to allocated."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        self._purge_expired_holds(rec)
        now = time.time()
        updated: List[SeatPublic] = []
        for label in req.seat_labels:
            seat = rec.seats.get(label)
            if not seat:
                raise KeyError(f"seat_not_found:{label}")
            if seat.status == SeatStatus.held:
                # allowed if not expired
                if not seat.hold_until or seat.hold_until <= now:
                    raise ValueError(f"hold_expired:{label}")
            elif seat.status != SeatStatus.available:
                raise ValueError(f"seat_unavailable:{label}")
            seat.status = SeatStatus.allocated
            seat.order_id = req.order_id
            seat.hold_until = None
            seat.hold_ref = None
            updated.append(SeatPublic(**seat.model_dump()))
        return updated

    # PUBLIC_INTERFACE
    def release_seats(self, venue_id: str, req: ReleaseSeatsRequest) -> List[SeatPublic]:
        """Release seats from held state back to available."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        updated: List[SeatPublic] = []
        for label in req.seat_labels:
            seat = rec.seats.get(label)
            if not seat:
                raise KeyError(f"seat_not_found:{label}")
            if seat.status == SeatStatus.held:
                seat.status = SeatStatus.available
                seat.hold_until = None
                seat.hold_ref = None
                updated.append(SeatPublic(**seat.model_dump()))
        return updated

    # PUBLIC_INTERFACE
    def block_seats(self, venue_id: str, labels: List[str]) -> List[SeatPublic]:
        """Block seats (admin/organizer operation)."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        out: List[SeatPublic] = []
        for l in labels:
            seat = rec.seats.get(l)
            if not seat:
                raise KeyError(f"seat_not_found:{l}")
            seat.status = SeatStatus.blocked
            seat.hold_until = None
            seat.hold_ref = None
            out.append(SeatPublic(**seat.model_dump()))
        return out

    # PUBLIC_INTERFACE
    def unblock_seats(self, venue_id: str, labels: List[str]) -> List[SeatPublic]:
        """Unblock seats back to available."""
        rec = self._venues.get(venue_id)
        if not rec:
            raise KeyError("venue_not_found")
        out: List[SeatPublic] = []
        for l in labels:
            seat = rec.seats.get(l)
            if not seat:
                raise KeyError(f"seat_not_found:{l}")
            if seat.status == SeatStatus.blocked:
                seat.status = SeatStatus.available
            out.append(SeatPublic(**seat.model_dump()))
        return out

    # PUBLIC_INTERFACE
    def analytics(self, venue_id: str) -> AnalyticsResponse:
        """Compute simple analytics for admin/organizer dashboards."""
        snapshot = self.get_availability(venue_id)
        occupancy = (snapshot.allocated / snapshot.total) if snapshot.total else 0.0
        held_rate = (snapshot.held / snapshot.total) if snapshot.total else 0.0
        return AnalyticsResponse(
            venue_id=venue_id,
            total_seats=snapshot.total,
            available=snapshot.available,
            held=snapshot.held,
            allocated=snapshot.allocated,
            blocked=snapshot.blocked,
            occupancy_rate=round(occupancy, 4),
            held_rate=round(held_rate, 4),
        )


# Global store instance for the app
STORE = InMemoryVenueStore()
