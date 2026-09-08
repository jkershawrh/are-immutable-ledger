use std::env;

use thiserror::Error;

#[derive(Debug, Clone)]
pub struct AppConfig {
    pub grpc_port: u16,
    pub health_port: u16,
    pub metrics_port: u16,
    pub max_content_size_bytes: usize,
    pub db_connection_string: String,
    pub outbox_http_endpoint: Option<String>,
    pub outbox_http_bearer_token: Option<String>,
    pub outbox_http_timeout_seconds: u64,
    pub genesis_hash_input: String,
    pub pool_max_size: usize,
    pub chain_max_retries: u32,
    pub chain_halt_recovery_seconds: u64,
    pub outbox_max_retries: u32,
    pub verify_interval_seconds: u64,
    pub verify_max_entries_per_chain: i64,
    pub api_token: Option<String>,
    pub shutdown_token: Option<String>,
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("missing required environment variable: {0}")]
    Missing(String),
    #[error("invalid integer value for {0}")]
    InvalidInteger(String),
}

impl AppConfig {
    pub fn from_env() -> Result<Self, ConfigError> {
        Ok(Self {
            grpc_port: parse_u16("ARE_LEDGER_GRPC_PORT", 9092)?,
            health_port: parse_u16("ARE_LEDGER_HEALTH_PORT", 8080)?,
            metrics_port: parse_u16("ARE_LEDGER_METRICS_PORT", 8083)?,
            max_content_size_bytes: parse_usize("ARE_LEDGER_MAX_CONTENT_SIZE_BYTES", 1_048_576)?,
            db_connection_string: required("ARE_LEDGER_DB_CONNECTION_STRING")?,
            outbox_http_endpoint: optional("ARE_LEDGER_OUTBOX_HTTP_ENDPOINT"),
            outbox_http_bearer_token: optional("ARE_LEDGER_OUTBOX_HTTP_BEARER_TOKEN"),
            outbox_http_timeout_seconds: parse_nonzero_u64(
                "ARE_LEDGER_OUTBOX_HTTP_TIMEOUT_SECONDS",
                10,
            )?,
            genesis_hash_input: env::var("ARE_LEDGER_GENESIS_HASH_INPUT")
                .unwrap_or_else(|_| "ARE_LEDGER_GENESIS".to_string()),
            pool_max_size: parse_usize("ARE_LEDGER_POOL_MAX_SIZE", 16)?,
            chain_max_retries: parse_usize("ARE_LEDGER_CHAIN_MAX_RETRIES", 10)? as u32,
            chain_halt_recovery_seconds: parse_nonzero_u64(
                "ARE_LEDGER_CHAIN_HALT_RECOVERY_SECONDS",
                60,
            )?,
            outbox_max_retries: parse_usize("ARE_LEDGER_OUTBOX_MAX_RETRIES", 10)? as u32,
            verify_interval_seconds: match env::var("ARE_LEDGER_VERIFY_INTERVAL_SECONDS") {
                Ok(raw) => raw.parse::<u64>().map_err(|_| {
                    ConfigError::InvalidInteger("ARE_LEDGER_VERIFY_INTERVAL_SECONDS".to_string())
                })?,
                Err(_) => 300,
            },
            verify_max_entries_per_chain: parse_positive_i64(
                "ARE_LEDGER_VERIFY_MAX_ENTRIES_PER_CHAIN",
                10_000,
            )?,
            api_token: env::var("ARE_LEDGER_API_TOKEN").ok(),
            shutdown_token: env::var("ARE_LEDGER_SHUTDOWN_TOKEN").ok(),
        })
    }
}

fn required(name: &str) -> Result<String, ConfigError> {
    env::var(name).map_err(|_| ConfigError::Missing(name.to_string()))
}

fn optional(name: &str) -> Option<String> {
    env::var(name).ok().filter(|value| !value.trim().is_empty())
}

fn parse_u16(name: &str, default: u16) -> Result<u16, ConfigError> {
    match env::var(name) {
        Ok(raw) => raw
            .parse::<u16>()
            .map_err(|_| ConfigError::InvalidInteger(name.to_string())),
        Err(_) => Ok(default),
    }
}

fn parse_usize(name: &str, default: usize) -> Result<usize, ConfigError> {
    match env::var(name) {
        Ok(raw) => raw
            .parse::<usize>()
            .map_err(|_| ConfigError::InvalidInteger(name.to_string())),
        Err(_) => Ok(default),
    }
}

fn parse_nonzero_u64(name: &str, default: u64) -> Result<u64, ConfigError> {
    let value = match env::var(name) {
        Ok(raw) => raw
            .parse::<u64>()
            .map_err(|_| ConfigError::InvalidInteger(name.to_string()))?,
        Err(_) => default,
    };
    if value == 0 {
        return Err(ConfigError::InvalidInteger(name.to_string()));
    }
    Ok(value)
}

fn parse_positive_i64(name: &str, default: i64) -> Result<i64, ConfigError> {
    let value = match env::var(name) {
        Ok(raw) => raw
            .parse::<i64>()
            .map_err(|_| ConfigError::InvalidInteger(name.to_string()))?,
        Err(_) => default,
    };
    if value <= 0 {
        return Err(ConfigError::InvalidInteger(name.to_string()));
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, OnceLock};

    fn env_lock() -> std::sync::MutexGuard<'static, ()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(())).lock().expect("lock")
    }

    fn clear() {
        let names = [
            "ARE_LEDGER_GRPC_PORT",
            "ARE_LEDGER_HEALTH_PORT",
            "ARE_LEDGER_METRICS_PORT",
            "ARE_LEDGER_MAX_CONTENT_SIZE_BYTES",
            "ARE_LEDGER_DB_CONNECTION_STRING",
            "ARE_LEDGER_OUTBOX_HTTP_ENDPOINT",
            "ARE_LEDGER_OUTBOX_HTTP_BEARER_TOKEN",
            "ARE_LEDGER_OUTBOX_HTTP_TIMEOUT_SECONDS",
            "ARE_LEDGER_GENESIS_HASH_INPUT",
            "ARE_LEDGER_OUTBOX_MAX_RETRIES",
            "ARE_LEDGER_VERIFY_INTERVAL_SECONDS",
            "ARE_LEDGER_VERIFY_MAX_ENTRIES_PER_CHAIN",
            "ARE_LEDGER_API_TOKEN",
            "ARE_LEDGER_SHUTDOWN_TOKEN",
        ];
        for name in names {
            std::env::remove_var(name);
        }
    }

    #[test]
    fn loads_defaults_and_required_values() {
        let _guard = env_lock();
        clear();
        std::env::set_var("ARE_LEDGER_DB_CONNECTION_STRING", "postgres://db");
        let cfg = AppConfig::from_env().expect("config");
        assert_eq!(cfg.grpc_port, 9092);
        assert_eq!(cfg.health_port, 8080);
        assert_eq!(cfg.metrics_port, 8083);
        assert_eq!(cfg.max_content_size_bytes, 1_048_576);
        assert_eq!(cfg.genesis_hash_input, "ARE_LEDGER_GENESIS");
        assert_eq!(cfg.outbox_http_timeout_seconds, 10);
        assert_eq!(cfg.verify_max_entries_per_chain, 10_000);
        assert!(cfg.outbox_http_endpoint.is_none());
    }

    #[test]
    fn missing_required_variable_fails() {
        let _guard = env_lock();
        clear();
        let err = AppConfig::from_env().expect_err("must fail");
        assert!(matches!(err, ConfigError::Missing(_)));
    }

    #[test]
    fn invalid_integer_fails() {
        let _guard = env_lock();
        clear();
        std::env::set_var("ARE_LEDGER_DB_CONNECTION_STRING", "postgres://db");
        std::env::set_var("ARE_LEDGER_GRPC_PORT", "not-a-number");
        let err = AppConfig::from_env().expect_err("must fail");
        assert!(matches!(err, ConfigError::InvalidInteger(_)));
    }

    #[test]
    fn rejects_zero_outbox_timeout() {
        let _guard = env_lock();
        clear();
        std::env::set_var("ARE_LEDGER_DB_CONNECTION_STRING", "postgres://db");
        std::env::set_var("ARE_LEDGER_OUTBOX_HTTP_TIMEOUT_SECONDS", "0");
        let err = AppConfig::from_env().expect_err("must fail");
        assert!(matches!(err, ConfigError::InvalidInteger(_)));
    }

    #[test]
    fn rejects_non_positive_verification_window() {
        let _guard = env_lock();
        clear();
        std::env::set_var("ARE_LEDGER_DB_CONNECTION_STRING", "postgres://db");
        std::env::set_var("ARE_LEDGER_VERIFY_MAX_ENTRIES_PER_CHAIN", "0");
        let err = AppConfig::from_env().expect_err("must fail");
        assert!(matches!(err, ConfigError::InvalidInteger(_)));
    }
}
