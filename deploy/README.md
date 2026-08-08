# Deployment notes

The Action deploys one container with `--network host`. This is intentional:
the target host already exposes PostgreSQL and Redis on `127.0.0.1`, so the
application can use the connection strings supplied by the operator without
exposing either data service to the public network.

The application listens on `0.0.0.0:8080`. Put it behind an existing reverse
proxy if the server already has one. The container name is fixed to
`hot-trend-monitor` so rollouts are idempotent.

