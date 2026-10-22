Thanks Ian — Thanks for the info. Greatly appreciate it! So taking what you explain that's the gap I just closed. The ledger now supports three layers of proof:

1. Hash chain— content wasn't modified (existing)
2. Writer signatures — opaque bytes (Ed25519, SPIFFE SVIDs, whatever the writer uses) + a key reference so the verifier knows which public key to check against
3. Attestation reports*— opaque bytes (SGX quotes, SEV-SNP reports, RATS EAT tokens) proving the runtime environment

All three are stored, none are verified by the ledger. It stays identity-neutral — stores the proof, returns it on VerifyProof, and lets the downstream verifier validate against their own trust infrastructure. 146 automated tests including signature replay, forged sig detection, and mixed signed/unsigned chains.

Would be great to hear more about the CoSAI remote attestation work — especially how the attestation report binds to the signing key. Happy to demo what we have or dig into the integration.
