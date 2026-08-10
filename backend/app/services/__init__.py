"""Business-logic orchestration, one module per domain. Routers stay thin —
they parse/validate the request and delegate to a service function, which
owns DB access + any cross-cutting concerns (encryption, adapter selection)."""
