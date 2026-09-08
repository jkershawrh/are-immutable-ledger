use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde::Serialize;
use tokio::sync::RwLock;
use tracing::{info, warn};

use crate::repository::LedgerRepository;
use crate::service::{EventPublisher, ImmutableLedgerService};

#[derive(Debug, Clone, Serialize)]
pub struct VerificationStatus {
    pub all_valid: bool,
    pub chains_checked: usize,
    pub last_run: DateTime<Utc>,
    pub duration_ms: u64,
    pub chain_results: Vec<ChainResult>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChainResult {
    pub entry_type: String,
    pub valid: bool,
    pub entries_checked: i64,
    pub failure_reason: String,
}

pub type SharedVerificationStatus = Arc<RwLock<Option<VerificationStatus>>>;

pub fn spawn_background_verifier<R, P>(
    service: Arc<ImmutableLedgerService<R, P>>,
    status: SharedVerificationStatus,
    interval: Duration,
    max_entries_per_chain: i64,
) where
    R: LedgerRepository + 'static,
    P: EventPublisher + 'static,
{
    tokio::spawn(async move {
        loop {
            let start = std::time::Instant::now();
            let chain_results = run_verification(&service, max_entries_per_chain).await;
            let all_valid = chain_results.iter().all(|r| r.valid);
            let verification = VerificationStatus {
                all_valid,
                chains_checked: chain_results.len(),
                last_run: Utc::now(),
                duration_ms: start.elapsed().as_millis() as u64,
                chain_results,
            };

            if all_valid {
                crate::metrics::CHAIN_INTEGRITY_VALID.set(1);
                info!(
                    chains = verification.chains_checked,
                    "background verification passed"
                );
            } else {
                crate::metrics::CHAIN_INTEGRITY_VALID.set(0);
                warn!(
                    chains = verification.chains_checked,
                    "background verification found invalid chain(s)"
                );
            }

            *status.write().await = Some(verification);
            tokio::time::sleep(interval).await;
        }
    });
}

async fn run_verification<R: LedgerRepository + 'static, P: EventPublisher + 'static>(
    service: &ImmutableLedgerService<R, P>,
    max_entries_per_chain: i64,
) -> Vec<ChainResult> {
    let entry_types = match service.get_distinct_entry_types().await {
        Ok(types) => types,
        Err(e) => {
            warn!("background verifier failed to get entry types: {e}");
            return Vec::new();
        }
    };
    let mut results = Vec::with_capacity(entry_types.len());
    for entry_type in entry_types {
        let result = match service
            .verify_recent_chain(&entry_type, max_entries_per_chain)
            .await
        {
            Ok(output) => ChainResult {
                entry_type,
                valid: output.chain_valid,
                entries_checked: output.entries_checked,
                failure_reason: output.failure_reason,
            },
            Err(e) => ChainResult {
                entry_type,
                valid: false,
                entries_checked: 0,
                failure_reason: format!("{e}"),
            },
        };
        results.push(result);
    }
    results
}
