from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    analytics_router,
    availability_router,
    health_router,
    seats_router,
    venues_router,
    allocation_router,
)


openapi_tags = [
    {"name": "health", "description": "Service health and metadata"},
    {"name": "venues", "description": "Venue CRUD operations"},
    {"name": "seats", "description": "Seat map and seat type configuration"},
    {"name": "availability", "description": "Real-time availability (REST + WebSocket)"},
    {"name": "allocation", "description": "Seat holding, releasing, and allocation"},
    {"name": "analytics", "description": "Admin/Organizer analytics"},
]

app = FastAPI(
    title=os.getenv("SERVICE_NAME", "Venue Service"),
    description=os.getenv(
        "SERVICE_DESCRIPTION",
        "Venue creation, seat mapping, and real-time availability service.",
    ),
    version=os.getenv("SERVICE_VERSION", "0.1.0"),
    openapi_tags=openapi_tags,
)

cors_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(venues_router)
app.include_router(seats_router)
app.include_router(availability_router)
app.include_router(allocation_router)
app.include_router(analytics_router)

# Convenience: docs note about websockets
@app.get(
    "/docs/websocket-usage",
    tags=["health"],
    summary="WebSocket usage notes",
    description=(
        "Connect to ws://<host>/venues/{venue_id}/availability/ws for real-time availability updates."
        " This demo uses an in-memory broadcast manager; production deployments should use a broker or pub/sub."
    ),
)
# PUBLIC_INTERFACE
def websocket_usage_note():
    """Describe WebSocket usage for consumers."""
    return {
        "websocket_endpoint": "/venues/{venue_id}/availability/ws",
        "notes": "Send any text to receive an updated availability snapshot.",
    }
