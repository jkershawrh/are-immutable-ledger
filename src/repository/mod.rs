mod postgres;

pub use postgres::PostgresLedgerRepository;

use std::collections::HashMap;
use std::sync::Arc;

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde_json::json;
use thiserror::Error;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::crypto::{canonical_entry_hash, CanonicalEntryHashInput};

#[derive(Debug, Clone)]
pub struct LedgerEntryRecord {
    pub entry_id: Uuid,
    pub entry_type: String,
    pub agent_id: String,
    pub content: Vec<u8>,
    pub content_type: String,
    pub source_id: String,
    pub correlation_id: Option<String>,
    pub idempotency_key: Option<String>,
    pub entry_hash: String,
    pub previous_hash: String,
    pub chain_position: i64,
    pub written_ts: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct OutboxRecord {
    pub outbox_id: Uuid,
    pub entry_id: Uuid,
    pub entry_type: String,
    pub payload: String,
    pub status: OutboxStatus,
    pub attempt_count: i32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OutboxStatus {
    Pending,
    Delivered,
    Failed,
}

#[derive(Debug, Clone)]
pub struct ChainTip {
    pub entry_id: Uuid,
    pub hash: String,
    pub position: i64,
    pub written_ts: DateTime<Utc>,
}

#[derive(Debug, Error, Clone)]
pub enum RepositoryError {
    #[error("entry not found")]
    NotFound,
    #[error("repository unavailable")]
    Unavailable,
    #[error("chain integrity violation")]
    ChainIntegrityViolation,
    #[error("idempotency key conflict")]
    IdempotencyConflict,
}

#[derive(Debug, Clone)]
pub struct WriteResult {
    pub entry: LedgerEntryRecord,
    pub outbox: OutboxRecord,
}

#[derive(Debug, Clone)]
pub struct EntryWriteInput {
    pub entry_type: String,
    pub agent_id: String,
    pub content: Vec<u8>,
    pub content_type: String,
    pub source_id: String,
    pub correlation_id: Option<String>,
    pub idempotency_key: Option<String>,
    pub previous_hash: String,
    pub written_ts: DateTime<Utc>,
}

#[derive(Debug, Clone, Default)]
pub struct EntryQuery {
    pub entry_type_prefix: Option<String>,
    pub agent_id: Option<String>,
    pub source_id: Option<String>,
    pub correlation_id: Option<String>,
    pub from_ts_ms: Option<i64>,
    pub to_ts_ms: Option<i64>,
    pub limit: usize,
    pub offset: usize,
}

#[derive(Debug, Clone)]
pub struct QueryResult {
    pub entries: Vec<LedgerEntryRecord>,
    pub total_count: i64,
}

#[async_trait]
pub trait LedgerRepository: Send + Sync {
    async fn write_entry_with_outbox(
        &self,
        input: EntryWriteInput,
    ) -> Result<WriteResult, RepositoryError>;
    async fn get_entry(&self, entry_id: Uuid) -> Result<LedgerEntryRecord, RepositoryError>;
    async fn query_entries(&self, query: EntryQuery) -> Result<QueryResult, RepositoryError>;
    async fn get_chain_tip(&self, entry_type: &str) -> Result<ChainTip, RepositoryError>;
    async fn get_entries_by_type(
        &self,
        entry_type: &str,
    ) -> Result<Vec<LedgerEntryRecord>, RepositoryError>;
    async fn find_idempotent(
        &self,
        entry_type: &str,
        idempotency_key: &str,
    ) -> Result<Option<LedgerEntryRecord>, RepositoryError>;
    async fn get_entry_by_hash(
        &self,
        entry_type: &str,
        entry_hash: &str,
    ) -> Result<LedgerEntryRecord, RepositoryError>;
    async fn pending_outbox(&self) -> Result<Vec<OutboxRecord>, RepositoryError>;
    async fn mark_outbox_delivered(&self, outbox_id: Uuid) -> Result<(), RepositoryError>;
}

#[derive(Default, Clone)]
pub struct InMemoryLedgerRepository {
    inner: Arc<RwLock<Inner>>,
}

#[derive(Default)]
struct Inner {
    entries: HashMap<Uuid, LedgerEntryRecord>,
    ordered_by_type: HashMap<String, Vec<Uuid>>,
    chain_tips: HashMap<String, ChainTip>,
    idempotency_index: HashMap<(String, String), Uuid>,
    outbox: HashMap<Uuid, OutboxRecord>,
}

#[async_trait]
impl LedgerRepository for InMemoryLedgerRepository {
    async fn write_entry_with_outbox(
        &self,
        input: EntryWriteInput,
    ) -> Result<WriteResult, RepositoryError> {
        let mut guard = self.inner.write().await;
        if let Some(key) = &input.idempotency_key {
            if guard
                .idempotency_index
                .contains_key(&(input.entry_type.clone(), key.clone()))
            {
                return Err(RepositoryError::IdempotencyConflict);
            }
        }
        let next_position = guard
            .chain_tips
            .get(&input.entry_type)
            .map(|tip| tip.position + 1)
            .unwrap_or(1);

        if next_position == 1 && input.previous_hash.is_empty() {
            return Err(RepositoryError::ChainIntegrityViolation);
        }
        if next_position > 1 {
            let tip = guard
                .chain_tips
                .get(&input.entry_type)
                .ok_or(RepositoryError::ChainIntegrityViolation)?;
            if tip.hash != input.previous_hash {
                return Err(RepositoryError::ChainIntegrityViolation);
            }
        }

        let entry_id = Uuid::new_v4();
        let outbox_id = Uuid::new_v4();
        let entry_hash = canonical_entry_hash(&CanonicalEntryHashInput {
            entry_id,
            entry_type: &input.entry_type,
            agent_id: &input.agent_id,
            content: &input.content,
            content_type: &input.content_type,
            source_id: &input.source_id,
            correlation_id: input.correlation_id.as_deref(),
            idempotency_key: input.idempotency_key.as_deref(),
            chain_position: next_position,
            written_ts_ms: input.written_ts.timestamp_millis(),
            previous_hash: &input.previous_hash,
        });
        let outbox_payload = ledger_written_payload(
            &entry_id,
            &input.entry_type,
            &input.agent_id,
            &input.source_id,
            &entry_hash,
            input.correlation_id.as_deref(),
            input.written_ts.timestamp_millis(),
        );
        let entry = LedgerEntryRecord {
            entry_id,
            entry_type: input.entry_type.clone(),
            agent_id: input.agent_id,
            content: input.content,
            content_type: input.content_type,
            source_id: input.source_id,
            correlation_id: input.correlation_id,
            idempotency_key: input.idempotency_key.clone(),
            entry_hash: entry_hash.clone(),
            previous_hash: input.previous_hash,
            chain_position: next_position,
            written_ts: input.written_ts,
        };
        let outbox = OutboxRecord {
            outbox_id,
            entry_id,
            entry_type: input.entry_type.clone(),
            payload: outbox_payload,
            status: OutboxStatus::Pending,
            attempt_count: 0,
        };

        guard.entries.insert(entry_id, entry.clone());
        guard
            .ordered_by_type
            .entry(input.entry_type.clone())
            .or_default()
            .push(entry_id);
        guard.chain_tips.insert(
            input.entry_type,
            ChainTip {
                entry_id,
                hash: entry_hash,
                position: next_position,
                written_ts: entry.written_ts,
            },
        );
        if let Some(key) = input.idempotency_key {
            guard
                .idempotency_index
                .insert((entry.entry_type.clone(), key), entry_id);
        }
        guard.outbox.insert(outbox_id, outbox.clone());
        Ok(WriteResult { entry, outbox })
    }

    async fn get_entry(&self, entry_id: Uuid) -> Result<LedgerEntryRecord, RepositoryError> {
        self.inner
            .read()
            .await
            .entries
            .get(&entry_id)
            .cloned()
            .ok_or(RepositoryError::NotFound)
    }

    async fn query_entries(&self, query: EntryQuery) -> Result<QueryResult, RepositoryError> {
        let guard = self.inner.read().await;
        let mut values: Vec<LedgerEntryRecord> = guard.entries.values().cloned().collect();
        apply_query_filters(&mut values, &query);
        values.sort_by_key(|entry| (entry.written_ts.timestamp_millis(), entry.chain_position));
        let total_count = values.len() as i64;
        let entries = values
            .into_iter()
            .skip(query.offset)
            .take(query.limit)
            .collect();
        Ok(QueryResult {
            entries,
            total_count,
        })
    }

    async fn get_chain_tip(&self, entry_type: &str) -> Result<ChainTip, RepositoryError> {
        self.inner
            .read()
            .await
            .chain_tips
            .get(entry_type)
            .cloned()
            .ok_or(RepositoryError::NotFound)
    }

    async fn get_entries_by_type(
        &self,
        entry_type: &str,
    ) -> Result<Vec<LedgerEntryRecord>, RepositoryError> {
        let guard = self.inner.read().await;
        let Some(ids) = guard.ordered_by_type.get(entry_type) else {
            return Ok(Vec::new());
        };
        let mut out = Vec::with_capacity(ids.len());
        for id in ids {
            if let Some(entry) = guard.entries.get(id) {
                out.push(entry.clone());
            }
        }
        Ok(out)
    }

    async fn get_entry_by_hash(
        &self,
        entry_type: &str,
        entry_hash: &str,
    ) -> Result<LedgerEntryRecord, RepositoryError> {
        let guard = self.inner.read().await;
        guard
            .entries
            .values()
            .find(|e| e.entry_type == entry_type && e.entry_hash == entry_hash)
            .cloned()
            .ok_or(RepositoryError::NotFound)
    }

    async fn find_idempotent(
        &self,
        entry_type: &str,
        idempotency_key: &str,
    ) -> Result<Option<LedgerEntryRecord>, RepositoryError> {
        let guard = self.inner.read().await;
        let Some(entry_id) = guard
            .idempotency_index
            .get(&(entry_type.to_string(), idempotency_key.to_string()))
        else {
            return Ok(None);
        };
        Ok(guard.entries.get(entry_id).cloned())
    }

    async fn pending_outbox(&self) -> Result<Vec<OutboxRecord>, RepositoryError> {
        let guard = self.inner.read().await;
        Ok(guard
            .outbox
            .values()
            .filter(|record| record.status == OutboxStatus::Pending)
            .cloned()
            .collect())
    }

    async fn mark_outbox_delivered(&self, outbox_id: Uuid) -> Result<(), RepositoryError> {
        let mut guard = self.inner.write().await;
        let Some(record) = guard.outbox.get_mut(&outbox_id) else {
            return Err(RepositoryError::NotFound);
        };
        record.status = OutboxStatus::Delivered;
        Ok(())
    }
}

pub fn ledger_written_payload(
    entry_id: &Uuid,
    entry_type: &str,
    agent_id: &str,
    source_id: &str,
    entry_hash: &str,
    correlation_id: Option<&str>,
    written_ts_ms: i64,
) -> String {
    json!({
        "event_id": Uuid::new_v4().to_string(),
        "event_type": "LEDGER_ENTRY_WRITTEN",
        "entry_id": entry_id.to_string(),
        "entry_type": entry_type,
        "agent_id": agent_id,
        "source_id": source_id,
        "entry_hash": entry_hash,
        "correlation_id": correlation_id,
        "written_ts": written_ts_ms,
        "schema_version": "1.0.0"
    })
    .to_string()
}

fn apply_query_filters(entries: &mut Vec<LedgerEntryRecord>, query: &EntryQuery) {
    if let Some(filter) = query.entry_type_prefix.as_deref() {
        entries.retain(|entry| entry.entry_type.starts_with(filter));
    }
    if let Some(filter) = query.agent_id.as_deref() {
        entries.retain(|entry| entry.agent_id == filter);
    }
    if let Some(filter) = query.source_id.as_deref() {
        entries.retain(|entry| entry.source_id == filter);
    }
    if let Some(filter) = query.correlation_id.as_deref() {
        entries.retain(|entry| entry.correlation_id.as_deref() == Some(filter));
    }
    if let Some(from) = query.from_ts_ms {
        entries.retain(|entry| entry.written_ts.timestamp_millis() >= from);
    }
    if let Some(to) = query.to_ts_ms {
        entries.retain(|entry| entry.written_ts.timestamp_millis() <= to);
    }
}

#[cfg(test)]
impl InMemoryLedgerRepository {
    /// Corrupts a stored entry hash (tests only).
    pub async fn test_corrupt_entry_hash(&self, entry_id: Uuid) -> bool {
        let mut g = self.inner.write().await;
        if let Some(e) = g.entries.get_mut(&entry_id) {
            e.entry_hash = "tampered-hash".to_string();
            return true;
        }
        false
    }

    /// Corrupts stored correlation metadata (tests only).
    pub async fn test_corrupt_correlation_id(&self, entry_id: Uuid, correlation_id: &str) -> bool {
        let mut g = self.inner.write().await;
        if let Some(e) = g.entries.get_mut(&entry_id) {
            e.correlation_id = Some(correlation_id.to_string());
            return true;
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use chrono::Utc;

    use super::*;

    #[tokio::test]
    async fn writes_and_reads_entry_with_tip_and_outbox() {
        let repo = InMemoryLedgerRepository::default();
        let result = repo
            .write_entry_with_outbox(EntryWriteInput {
                entry_type: "TYPE".to_string(),
                agent_id: "agent".to_string(),
                content: b"payload".to_vec(),
                content_type: "application/json".to_string(),
                source_id: "source".to_string(),
                correlation_id: None,
                idempotency_key: Some("idem".to_string()),
                previous_hash: "genesis".to_string(),
                written_ts: Utc::now(),
            })
            .await
            .expect("write");
        let fetched = repo.get_entry(result.entry.entry_id).await.expect("get");
        assert!(!fetched.entry_hash.is_empty());
        let tip = repo.get_chain_tip("TYPE").await.expect("tip");
        assert_eq!(tip.position, 1);
        let pending = repo.pending_outbox().await.expect("outbox");
        assert_eq!(pending.len(), 1);
        repo.mark_outbox_delivered(result.outbox.outbox_id)
            .await
            .expect("mark delivered");
        let pending_after = repo.pending_outbox().await.expect("outbox");
        assert!(pending_after.is_empty());
    }

    #[tokio::test]
    async fn rejects_chain_integrity_violation() {
        let repo = InMemoryLedgerRepository::default();
        let _ = repo
            .write_entry_with_outbox(EntryWriteInput {
                entry_type: "TYPE".to_string(),
                agent_id: "agent".to_string(),
                content: b"payload".to_vec(),
                content_type: "application/json".to_string(),
                source_id: "source".to_string(),
                correlation_id: None,
                idempotency_key: None,
                previous_hash: "genesis".to_string(),
                written_ts: Utc::now(),
            })
            .await
            .expect("first");
        let err = repo
            .write_entry_with_outbox(EntryWriteInput {
                entry_type: "TYPE".to_string(),
                agent_id: "agent".to_string(),
                content: b"payload-2".to_vec(),
                content_type: "application/json".to_string(),
                source_id: "source".to_string(),
                correlation_id: None,
                idempotency_key: None,
                previous_hash: "wrong-prev".to_string(),
                written_ts: Utc::now(),
            })
            .await
            .expect_err("should fail");
        assert!(matches!(err, RepositoryError::ChainIntegrityViolation));
    }
}
