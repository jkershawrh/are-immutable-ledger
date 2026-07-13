use std::sync::Arc;

use are_immutable_ledger::config::AppConfig;
use are_immutable_ledger::crypto::sha256_hex;
use are_immutable_ledger::repository::InMemoryLedgerRepository;
use are_immutable_ledger::service::{
    ImmutableLedgerService, NoopEventPublisher, QueryEntriesInput, WriteEntryInput,
};

fn config() -> Arc<AppConfig> {
    Arc::new(AppConfig {
        grpc_port: 9092,
        health_port: 8080,
        metrics_port: 8083,
        max_content_size_bytes: 1_048_576,
        db_connection_string: "postgres://local/test".to_string(),
        read_replica_connection_string: None,
        kafka_bootstrap_servers: "localhost:9092".to_string(),
        kafka_sasl_username: "user".to_string(),
        kafka_sasl_password: "pass".to_string(),
        genesis_hash_input: "ARE_LEDGER_GENESIS".to_string(),
        api_token: None,
        shutdown_token: None,
    })
}

fn entry(
    entry_type: &str,
    agent_id: &str,
    source_id: &str,
    correlation_id: &str,
    idempotency_key: &str,
    content: &[u8],
) -> WriteEntryInput {
    WriteEntryInput {
        entry_type: entry_type.to_string(),
        agent_id: agent_id.to_string(),
        content: content.to_vec(),
        content_type: "application/json".to_string(),
        source_id: source_id.to_string(),
        correlation_id: Some(correlation_id.to_string()),
        idempotency_key: Some(idempotency_key.to_string()),
        input_hash: Some(sha256_hex(content)),
        writer_signature: None,
        signer_key_reference: None,
        attestation_report: None,
    }
}

#[tokio::test]
async fn core_four_entries_are_correlated_receipted_and_chain_verifiable() {
    let service = ImmutableLedgerService::new(
        Arc::new(InMemoryLedgerRepository::default()),
        Arc::new(NoopEventPublisher),
        config(),
    );
    let correlation_id = "fleet-decision-01HZXK5QY4D3M8T7J2P6N9R0AV";

    let forecast = br#"{"specversion":"1.0","type":"io.srex.deepfield.forecast.v1","dataschema":"urn:srex:deepfield:schema:forecast:v1","risk":"capacity","revision":1}"#;
    let revised_forecast = br#"{"specversion":"1.0","type":"io.srex.deepfield.forecast.v1","dataschema":"urn:srex:deepfield:schema:forecast:v1","risk":"capacity","revision":2}"#;
    let decision =
        br#"{"specversion":"1.0","type":"ai.llm-d.gcl.decision-package.v1","schema_version":"gcl.llm-d.ai/decision-package/v1","action_class":"fleet.scale","confidence":0.91}"#;
    let outcome = br#"{"apiVersion":"fleet.llm-d.ai/v1beta1","kind":"FleetOperation","phase":"VERIFIED","observedReplicas":2}"#;

    let receipts = vec![
        service
            .issue_receipt(entry(
                "io.srex.deepfield.forecast.v1",
                "fleet-evidence-publisher",
                "urn:fleet-llm-d:evidence/deepfield",
                correlation_id,
                "deepfield:forecast:01HZXK5QY4D3M8T7J2P6N9R0AV",
                forecast,
            ))
            .await
            .expect("issue DeepField forecast receipt"),
        service
            .issue_receipt(entry(
                "io.srex.deepfield.forecast.v1",
                "fleet-evidence-publisher",
                "urn:fleet-llm-d:evidence/deepfield",
                correlation_id,
                "deepfield:forecast:01HZXK5QY4D3M8T7J2P6N9R0AV:revision-2",
                revised_forecast,
            ))
            .await
            .expect("issue revised DeepField forecast receipt"),
        service
            .issue_receipt(entry(
                "ai.llm-d.gcl.decision-package.v1",
                "governed-cognitive-loop",
                "urn:governed-cognitive-loop:decision",
                correlation_id,
                "gcl:decision:01HZXK5QY4D3M8T7J2P6N9R0AV",
                decision,
            ))
            .await
            .expect("issue decision-package receipt"),
        service
            .issue_receipt(entry(
                "fleet.operation.verified",
                "fleet-controller",
                "urn:fleet-llm-d:controller",
                correlation_id,
                "fleet:operation:01HZXK5QY4D3M8T7J2P6N9R0AV:verified",
                outcome,
            ))
            .await
            .expect("issue fleet outcome-transition receipt"),
    ];

    for receipt in &receipts {
        let proof = service
            .verify_proof(&receipt.entry_type, &receipt.entry_hash)
            .await
            .expect("verify proof receipt");
        assert!(proof.valid, "{} receipt must be valid", receipt.entry_type);
        assert_eq!(proof.correlation_id, correlation_id);
        assert_eq!(proof.input_hash, receipt.input_hash);
    }

    let (timeline, next_page, total_count) = service
        .query_entries(QueryEntriesInput {
            correlation_id: Some(correlation_id.to_string()),
            page_size: 10,
            ..QueryEntriesInput::default()
        })
        .await
        .expect("query correlated ecosystem entries");
    assert_eq!(total_count, 4);
    assert_eq!(timeline.len(), 4);
    assert!(next_page.is_none());
    assert!(timeline
        .iter()
        .all(|item| item.correlation_id.as_deref() == Some(correlation_id)));

    for (entry_type, expected_entries) in [
        ("io.srex.deepfield.forecast.v1", 2),
        ("ai.llm-d.gcl.decision-package.v1", 1),
        ("fleet.operation.verified", 1),
    ] {
        let verification = service
            .verify_chain(entry_type, None, None)
            .await
            .expect("verify producer chain");
        assert!(verification.chain_valid, "{entry_type} chain must be valid");
        assert_eq!(verification.entries_checked, expected_entries);
    }

    assert_eq!(receipts[0].chain_position, 1);
    assert_eq!(receipts[1].chain_position, 2);
}
