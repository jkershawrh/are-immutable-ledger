"""Thin Python client for the Immutable Ledger gRPC service."""

import sys
import os
import uuid

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "generated"))
import immutable_ledger_pb2 as pb
import immutable_ledger_pb2_grpc as pb_grpc


class LedgerClient:
    def __init__(self, endpoint="localhost:19292", api_token=None):
        self.channel = grpc.insecure_channel(endpoint, options=[
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ])
        self.stub = pb_grpc.ImmutableLedgerServiceStub(self.channel)
        token = api_token or os.environ.get("ARE_LEDGER_API_TOKEN", "")
        self.metadata = (("authorization", f"Bearer {token}"),) if token else None

    def _call(self, method, request):
        if self.metadata:
            return method(request, metadata=self.metadata)
        return method(request)

    def write(self, entry_type, agent_id, content, *, content_type="application/json",
              source_id="", correlation_id="", idempotency_key="", input_hash="",
              writer_signature=b"", signer_key_reference="", attestation_report=b""):
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())
        req = pb.WriteEntryRequest(
            entry_type=entry_type,
            agent_id=agent_id,
            content=content,
            content_type=content_type,
            source_id=source_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            writer_signature=writer_signature,
            signer_key_reference=signer_key_reference,
            attestation_report=attestation_report,
        )
        return self._call(self.stub.WriteEntry, req)

    def get_entry(self, entry_id):
        return self._call(self.stub.GetEntry, pb.GetEntryRequest(entry_id=entry_id)).entry

    def query(self, *, agent_id="", entry_type="", source_id="",
              correlation_id="", from_ts=0, to_ts=0, page_size=100):
        req = pb.QueryEntriesRequest(
            agent_id=agent_id,
            entry_type=entry_type,
            source_id=source_id,
            correlation_id=correlation_id,
            from_ts=from_ts,
            to_ts=to_ts,
            page_size=page_size,
        )
        resp = self._call(self.stub.QueryEntries, req)
        entries = list(resp.entries)
        while resp.next_page_token:
            req.page_token = resp.next_page_token
            resp = self._call(self.stub.QueryEntries, req)
            entries.extend(resp.entries)
        return entries

    def verify_entry(self, entry_id):
        return self._call(self.stub.VerifyEntry, pb.VerifyEntryRequest(entry_id=entry_id))

    def verify_chain(self, entry_type):
        return self._call(self.stub.VerifyChain, pb.VerifyChainRequest(entry_type=entry_type))

    def get_chain_tip(self, entry_type):
        return self._call(self.stub.GetChainTip, pb.GetChainTipRequest(entry_type=entry_type))

    def issue_receipt(self, entry_type, agent_id, content, *, content_type="application/json",
                      source_id="", correlation_id="", idempotency_key="", input_hash="",
                      writer_signature=b"", signer_key_reference="", attestation_report=b""):
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())
        req = pb.WriteEntryRequest(
            entry_type=entry_type, agent_id=agent_id, content=content,
            content_type=content_type, source_id=source_id,
            correlation_id=correlation_id, idempotency_key=idempotency_key,
            input_hash=input_hash,
            writer_signature=writer_signature,
            signer_key_reference=signer_key_reference,
            attestation_report=attestation_report,
        )
        return self._call(self.stub.IssueReceipt, req)

    def verify_proof(self, entry_hash, entry_type):
        return self._call(self.stub.VerifyProof,
                         pb.VerifyProofRequest(entry_hash=entry_hash, entry_type=entry_type))

    def get_entry_by_hash(self, entry_hash, entry_type):
        return self._call(self.stub.GetEntryByHash,
                         pb.GetEntryByHashRequest(entry_hash=entry_hash, entry_type=entry_type)).entry

    def close(self):
        self.channel.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
