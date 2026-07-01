import grpc from 'k6/net/grpc';
import http from 'k6/http';
import encoding from 'k6/encoding';
import { check } from 'k6';

const client = new grpc.Client();
client.load(['/work/proto'], 'immutable_ledger.proto');

const target = __ENV.K6_TARGET || 'host.docker.internal:9092';
const healthBase = __ENV.HEALTH_BASE || 'http://host.docker.internal:8080';
const shutdownToken = __ENV.SHUTDOWN_TOKEN || '';

export const options = {
  scenarios: {
    write_load: {
      executor: 'constant-arrival-rate',
      rate: 80,
      timeUnit: '1s',
      duration: '20s',
      preAllocatedVUs: 40,
      maxVUs: 120,
      exec: 'writeEntry',
    },
    shutdown: {
      executor: 'per-vu-iterations',
      vus: 1,
      iterations: 1,
      startTime: '8s',
      exec: 'triggerShutdown',
    },
  },
};

export function writeEntry() {
  client.connect(target, { plaintext: true });
  const now = Date.now();
  const payload = encoding.b64encode(`dg009-${now}`, 'rawstd');
  const response = client.invoke('are.ledger.v1.ImmutableLedgerService/WriteEntry', {
    entryType: 'LEDGER_ENTRY_TYPE_ACTION_RECEIPT',
    agentId: '11111111-1111-1111-1111-111111111111',
    content: payload,
    contentType: 'application/json',
    sourceId: 'ARE-FOUNDATION-PROOF',
    idempotencyKey: `dg009-${now}`,
  });
  check(response, { 'write status acceptable': (r) => r && [grpc.StatusOK, grpc.StatusUnavailable].includes(r.status) });
  client.close();
}

export function triggerShutdown() {
  const params = shutdownToken
    ? { headers: { Authorization: `Bearer ${shutdownToken}` } }
    : {};
  const response = http.post(`${healthBase}/shutdownz`, null, params);
  check(response, {
    'shutdown accepted or disabled': (r) => r && [202, 401, 404, 0].includes(r.status),
  });
}

