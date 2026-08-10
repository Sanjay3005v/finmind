"""Broker adapter layer.

`BrokerAdapter` (base.py) defines a broker-agnostic interface; business
logic (services/routers) must only ever depend on that ABC + the DTOs in
`schemas.py`, obtained via `registry.get_adapter(broker, mode, credentials)`.
Never branch on which concrete broker is in use outside this package.
"""
