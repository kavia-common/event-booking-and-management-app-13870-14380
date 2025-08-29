# VenueService

FastAPI service for venue and seating management:
- Venue CRUD
- Seat map definition and seat types
- Real-time availability (REST and WebSocket)
- Seat hold/release/allocate flows
- Basic analytics for organizers/admins

This implementation uses an in-memory store as a stub database. Replace with a real datastore for production.

## Quick start

1. Copy `.env.example` to `.env` and adjust values as needed.
2. Install dependencies:
   pip install -r requirements.txt
3. Run the service:
   uvicorn src.api.main:app --reload --port 3002

Open API docs at: http://localhost:3002/docs

Generate OpenAPI JSON:
   python -m src.api.generate_openapi

The JSON will be written to `interfaces/openapi.json`.

## Security and RBAC

- API Gateway is expected to authenticate users and forward the caller context via headers (e.g., `x-user-id`, `x-user-roles`).
- For local development, set `AUTH_DISABLED=true` (default). In this mode, role checks pass permissively.
- Endpoints that change state require `organizer` or `admin` roles. Read-only endpoints allow anonymous.
- Replace `src/api/security.py` with production-grade token validation (OAuth2/JWT or signed headers).

## WebSocket

- Connect to `/venues/{venue_id}/availability/ws` for availability snapshots.
- This stub broadcasts within a single process only. Use a broker/pub/sub for multi-instance deployments.

## Integration with other services

- BookingService:
  - Use `/venues/{venue_id}/allocation/hold` before payment to prevent race conditions.
  - Confirm seats with `/venues/{venue_id}/allocation/allocate` after payment authorization.
  - If payment fails/aborted, call `/venues/{venue_id}/allocation/release`.

- EventService:
  - Associate events with a `venue_id` from this service.
  - Use `/venues/{venue_id}/seats/map` and `/venues/{venue_id}/seats/types` to present seat maps and legends.

- API Gateway:
  - Centralize authN/Z and pass caller roles via headers to this service.
  - Optionally, aggregate availability data for dashboards.

## Data contracts (high level)

- VenuePublic
- SeatMapUpsert / SeatDefinition
- SeatTypeConfig
- AvailabilityResponse
- SeatHoldRequest / SeatAllocationRequest / ReleaseSeatsRequest

## Notes

- The in-memory store is not thread-safe for high concurrency. It is sufficient for demos/tests.
- Holds expire automatically upon read/update operations; consider a background sweeper for production.
- Replace the in-memory connection manager with a broadcast layer (e.g., Redis Pub/Sub) for horizontal scaling.
