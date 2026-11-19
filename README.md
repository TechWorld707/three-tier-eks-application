# Three-Tier EKS Application

Frontend and API application built by GitHub Actions and deployed to Amazon EKS through Argo CD.

## Observability

The backend exposes Prometheus metrics at `/metrics` on its internal HTTP service.
Gunicorn aggregates metrics across its workers. Request metrics group by Flask
route, method, and status, and exclude health and scrape requests. Pool metrics
track checked-out SQLAlchemy connections and checkout timeouts.

Set `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` to an OTLP/HTTP endpoint to enable Flask
and SQLAlchemy traces. The GitOps deployment samples 10% of requests without a
parent trace. Application and Nginx access logs are JSON. Use `request_id` to
correlate Nginx and backend records, and a sampled backend record's `trace_id` to
open the corresponding trace in Grafana Explore.
