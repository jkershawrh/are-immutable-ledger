#![forbid(unsafe_code)]

use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use anyhow::Context;
use axum::{
    http::{header, HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use tokio::net::TcpListener;
use tokio::sync::watch;
use tonic::{transport::Server, Status};
use tracing::{info, warn};

use are_immutable_ledger::config::AppConfig;
use are_immutable_ledger::db_permissions::verify_ledger_entries_immutable;
use are_immutable_ledger::grpc::pb::immutable_ledger_service_server::ImmutableLedgerServiceServer;
use are_immutable_ledger::grpc::ImmutableLedgerGrpc;
use are_immutable_ledger::metrics;
use are_immutable_ledger::repository::PostgresLedgerRepository;
use are_immutable_ledger::service::{HttpEventPublisher, ImmutableLedgerService};
use are_immutable_ledger::verifier::{self, SharedVerificationStatus};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .json()
        .with_current_span(false)
        .with_span_list(false)
        .init();

    let config = Arc::new(AppConfig::from_env().context("failed to load config")?);
    info!(
        grpc_port = config.grpc_port,
        health_port = config.health_port,
        metrics_port = config.metrics_port,
        "immutable ledger starting"
    );
    match verify_ledger_entries_immutable(&config.db_connection_string).await {
        Ok(_) => info!("verified DB permissions: ledger_entries is immutable for current role"),
        Err(err) => {
            warn!("DB permission verification failed: {err}");
            return Err(anyhow::anyhow!("db permission verification failed: {err}"));
        }
    }

    let pool = build_pool(&config).context("postgres pool creation")?;
    let pool_for_health = pool.clone();
    let repo = Arc::new(PostgresLedgerRepository::new(pool));
    let publisher = Arc::new(
        HttpEventPublisher::new(
            config.outbox_http_endpoint.clone(),
            config.outbox_http_bearer_token.clone(),
            Duration::from_secs(config.outbox_http_timeout_seconds),
        )
        .map_err(anyhow::Error::msg)
        .context("failed to configure outbox HTTP publisher")?,
    );
    info!(
        outbox_http_enabled = config.outbox_http_endpoint.is_some(),
        "configured outbox publisher"
    );
    let service = Arc::new(ImmutableLedgerService::new(repo, publisher, config.clone()));

    let verification_status: SharedVerificationStatus = Arc::new(tokio::sync::RwLock::new(None));

    if config.verify_interval_seconds > 0 {
        verifier::spawn_background_verifier(
            Arc::clone(&service),
            Arc::clone(&verification_status),
            Duration::from_secs(config.verify_interval_seconds),
            config.verify_max_entries_per_chain,
        );
        info!(
            interval_seconds = config.verify_interval_seconds,
            max_entries_per_chain = config.verify_max_entries_per_chain,
            "background chain verifier started"
        );
    }

    let grpc = ImmutableLedgerGrpc::new(service);

    let grpc_addr = SocketAddr::from(([0, 0, 0, 0], config.grpc_port));
    let health_addr = SocketAddr::from(([0, 0, 0, 0], config.health_port));
    let metrics_addr = SocketAddr::from(([0, 0, 0, 0], config.metrics_port));
    let (shutdown_tx, _) = watch::channel(false);
    let api_token = config.api_token.clone();
    let shutdown_token = config.shutdown_token.clone();

    {
        let shutdown_tx = shutdown_tx.clone();
        tokio::spawn(async move {
            let _ = wait_for_shutdown_signal().await;
            let _ = shutdown_tx.send(true);
        });
    }

    let mut grpc_shutdown_rx = shutdown_tx.subscribe();
    let grpc_server = tokio::spawn(async move {
        if let Some(api_token) = api_token {
            Server::builder()
                .add_service(ImmutableLedgerServiceServer::with_interceptor(
                    grpc,
                    move |request: tonic::Request<()>| authorize_grpc_request(request, &api_token),
                ))
                .serve_with_shutdown(grpc_addr, async move {
                    let _ = grpc_shutdown_rx.changed().await;
                })
                .await
        } else {
            Server::builder()
                .add_service(ImmutableLedgerServiceServer::new(grpc))
                .serve_with_shutdown(grpc_addr, async move {
                    let _ = grpc_shutdown_rx.changed().await;
                })
                .await
        }
    });

    let shutdown_tx_for_route = shutdown_tx.clone();
    let pool_for_ready = pool_for_health.clone();
    let status_for_ready = Arc::clone(&verification_status);
    let status_for_verify = Arc::clone(&verification_status);
    let app = Router::new()
        .route("/healthz", get(|| async { "ok" }))
        .route(
            "/readyz",
            get(move || {
                let pool = pool_for_ready.clone();
                let status = status_for_ready.clone();
                async move {
                    if pool.get().await.is_err() {
                        return (StatusCode::SERVICE_UNAVAILABLE, "database unavailable");
                    }
                    if let Some(ref v) = *status.read().await {
                        if !v.all_valid {
                            return (StatusCode::SERVICE_UNAVAILABLE, "chain verification failed");
                        }
                    }
                    (StatusCode::OK, "ready")
                }
            }),
        )
        .route(
            "/verifyz",
            get(move || {
                let status = status_for_verify.clone();
                async move {
                    let guard = status.read().await;
                    match &*guard {
                        Some(v) => axum::Json(serde_json::json!(v)).into_response(),
                        None => {
                            axum::Json(serde_json::json!({"status": "not_yet_run"})).into_response()
                        }
                    }
                }
            }),
        )
        .route(
            "/shutdownz",
            post(move |headers: HeaderMap| {
                let shutdown_tx = shutdown_tx_for_route.clone();
                let shutdown_token = shutdown_token.clone();
                async move {
                    let Some(token) = shutdown_token else {
                        return StatusCode::NOT_FOUND;
                    };
                    if !authorized_http(&headers, &token) {
                        return StatusCode::UNAUTHORIZED;
                    }
                    let _ = shutdown_tx.send(true);
                    StatusCode::ACCEPTED
                }
            }),
        );
    let listener = TcpListener::bind(health_addr)
        .await
        .context("failed to bind health listener")?;
    let mut health_shutdown_rx = shutdown_tx.subscribe();
    let health_server = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(async move {
                let _ = health_shutdown_rx.changed().await;
            })
            .await
    });

    let metrics_app = Router::new().route(
        "/metrics",
        get(|| async {
            let body = metrics::encode_prometheus();
            (
                [(
                    header::CONTENT_TYPE,
                    "text/plain; version=0.0.4; charset=utf-8",
                )],
                body,
            )
        }),
    );
    let metrics_listener = TcpListener::bind(metrics_addr)
        .await
        .context("failed to bind metrics listener")?;
    let mut metrics_shutdown_rx = shutdown_tx.subscribe();
    let metrics_server = tokio::spawn(async move {
        axum::serve(metrics_listener, metrics_app)
            .with_graceful_shutdown(async move {
                let _ = metrics_shutdown_rx.changed().await;
            })
            .await
    });

    let (grpc_result, health_result, metrics_result) =
        tokio::try_join!(grpc_server, health_server, metrics_server)?;
    grpc_result.context("gRPC server failed")?;
    health_result.context("health server failed")?;
    metrics_result.context("metrics server failed")?;
    Ok(())
}

fn authorize_grpc_request(
    request: tonic::Request<()>,
    api_token: &str,
) -> Result<tonic::Request<()>, Status> {
    let expected = format!("Bearer {api_token}");
    let authorized = request
        .metadata()
        .get("authorization")
        .and_then(|value| value.to_str().ok())
        .is_some_and(|actual| constant_time_eq(actual.as_bytes(), expected.as_bytes()));
    if authorized {
        Ok(request)
    } else {
        Err(Status::unauthenticated("missing or invalid bearer token"))
    }
}

fn authorized_http(headers: &HeaderMap, token: &str) -> bool {
    let expected = format!("Bearer {token}");
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|actual| constant_time_eq(actual.as_bytes(), expected.as_bytes()))
}

/// Constant-time byte comparison to prevent timing side-channels on token checks.
/// Always iterates all bytes of both inputs; returns false immediately only on length mismatch.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff: u8 = 0;
    for (x, y) in a.iter().zip(b.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}

fn build_pool(config: &AppConfig) -> anyhow::Result<deadpool_postgres::Pool> {
    let pg_config: tokio_postgres::Config =
        config.db_connection_string.parse().with_context(|| {
            format!(
                "parsing db_connection_string: {}",
                config.db_connection_string
            )
        })?;
    let tls_connector = are_immutable_ledger::tls::make_pg_tls(&config.db_connection_string)
        .context("configuring postgres TLS")?;
    let manager = deadpool_postgres::Manager::new(pg_config, tls_connector);
    let pool = deadpool_postgres::Pool::builder(manager)
        .max_size(config.pool_max_size)
        .build()
        .context("building connection pool")?;
    info!(
        pool_max_size = config.pool_max_size,
        "postgres connection pool created"
    );
    Ok(pool)
}

async fn wait_for_shutdown_signal() -> anyhow::Result<()> {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{signal, SignalKind};
        let mut terminate = signal(SignalKind::terminate())?;
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {}
            _ = terminate.recv() => {}
        }
    }
    #[cfg(not(unix))]
    {
        tokio::signal::ctrl_c().await?;
    }
    Ok(())
}
