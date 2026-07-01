import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Header } from './components/Header'
import { SystemDiagram } from './components/SystemDiagram'
import { ChainView } from './components/ChainView'
import { TimelineView } from './components/TimelineView'
import { VerifyView } from './components/VerifyView'
import { DriftView } from './components/DriftView'
import { ReceiptFlow } from './components/ReceiptFlow'
import { StatsBar } from './components/StatsBar'
import { useFetch } from './hooks/useLedger'
import { api } from './api/ledgerApi'

const ACTS = ['story', 'architecture', 'chains', 'timeline', 'receipts', 'ordeal', 'reward', 'return'] as const
type Act = typeof ACTS[number]

const NEXT_LABELS: Record<Act, string> = {
  story: 'See the architecture',
  architecture: 'Explore the chains',
  chains: 'View the timeline',
  timeline: 'See proof receipts',
  receipts: 'Face the ordeal',
  ordeal: 'Claim the reward',
  reward: 'Return with proof',
  return: '',
}

export default function App() {
  const [started, setStarted] = useState(false)
  const [actIndex, setActIndex] = useState(0)
  const { data: summary } = useFetch(() => api.summary(), [])

  const currentAct = ACTS[actIndex]
  const nextLabel = NEXT_LABELS[currentAct]

  const goNext = () => { if (actIndex < ACTS.length - 1) setActIndex(actIndex + 1) }
  const goBack = () => { if (actIndex > 0) setActIndex(actIndex - 1) }

  if (!started) {
    return (
      <div
        onClick={() => setStarted(true)}
        style={{
          height: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          background: 'var(--bg-dark)',
        }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1 }}
          style={{
            width: 64, height: 64, borderRadius: 16,
            background: 'linear-gradient(135deg, var(--blue), var(--purple))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 32, marginBottom: 24,
          }}
        >⛓</motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.8 }}
          style={{ fontSize: 22, fontWeight: 900, fontFamily: 'var(--font-display)', letterSpacing: 3, marginBottom: 8 }}
        >
          IMMUTABLE LEDGER
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.8 }}
          style={{ fontSize: 13, color: 'var(--text-dim)', letterSpacing: 1, marginBottom: 48 }}
        >
          cross-system proof chain for agentic systems
        </motion.div>
        <motion.div
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ repeat: Infinity, duration: 2.5 }}
          style={{ fontSize: 12, color: 'var(--text-disabled)' }}
        >
          click to begin
        </motion.div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-dark)' }}>
      <Header />

      {/* Act progress dots */}
      <div style={{
        display: 'flex', justifyContent: 'center', gap: 6, padding: '12px 0',
        borderBottom: '1px solid var(--border)', background: 'var(--bg-dark)',
      }}>
        {ACTS.map((act, i) => (
          <div
            key={act}
            onClick={() => i <= actIndex && setActIndex(i)}
            style={{
              width: 8, height: 8, borderRadius: '50%',
              background: i === actIndex ? 'var(--blue)' : i < actIndex ? 'var(--green)' : 'var(--surface-3)',
              cursor: i <= actIndex ? 'pointer' : 'default',
              transition: 'background 0.3s',
            }}
          />
        ))}
      </div>

      {/* Act content */}
      <div style={{ flex: 1, maxWidth: 960, margin: '0 auto', padding: '32px 24px', width: '100%' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={currentAct}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 }}
            transition={{ duration: 0.3 }}
          >

            {/* ACT 0 — THE ORDINARY WORLD */}
            {currentAct === 'story' && (
              <div>
                <h3 style={{ marginBottom: 20 }}><SectionNum n="00" /> The Ordinary World</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 15, lineHeight: 1.7, marginBottom: 24, maxWidth: 700 }}>
                  Autonomous agents are running in production. Every platform logs what they do. None of them can prove it across system boundaries.
                </p>
                <div style={{ maxWidth: 700 }}>
                  <StoryStep num="1" text="OpenShell sandboxes agents and emits OCSF security events — network allows, denials, process launches. The events go to JSONL files that can be edited or deleted after the fact." />
                  <StoryStep num="2" text="Kagenti orchestrates agent fleets and captures OTEL traces — tool calls, LLM requests, agent lifecycle. The traces go to Phoenix or Jaeger — separate systems with no cryptographic link to what the sandbox enforced." />
                  <StoryStep num="3" text="Governance systems evaluate authority — passports, scoped permissions, policy decisions. But those decisions live in a different database than the sandbox events or the agent traces. Nothing ties them together." />
                  <StoryStep num="4" text="Existing immutable databases (QLDB, immudb) are single-system stores. They can prove entries weren't tampered with — but they can't correlate across independent systems with different identities and formats. When compliance asks 'prove what this agent did end-to-end,' nobody has a unified, verifiable answer." />
                </div>
              </div>
            )}

            {/* ACT 1 — THE CALL: ARCHITECTURE */}
            {currentAct === 'architecture' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="01" /> The Call to Adventure</h3>
                <SectionContext lines={[
                  'What if every system wrote its events — in its own format, with its own identity — to a shared proof chain with independent per-source verification?',
                  'Not a replacement for QLDB or immudb. A cross-system layer that sits above them. Each source keeps its own hash chain. A single query correlates across all sources by trace ID, agent ID, or time range.',
                ]} />
                <SystemDiagram />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
                  <div className="card" style={{ borderColor: 'var(--border)' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', fontFamily: 'var(--font-display)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
                      Write
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      <span style={{ color: 'var(--purple)' }}>IssueReceipt</span>{'('}<br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>entry_type:</span> <span style={{ color: 'var(--green)' }}>"guardrail.pii_scan"</span><br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>agent_id:</span> <span style={{ color: 'var(--green)' }}>"authbridge-proxy"</span><br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>content:</span> <span style={{ color: 'var(--green)' }}>{'{'}"result":"clean"{'}'}</span><br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>correlation_id:</span> <span style={{ color: 'var(--green)' }}>"trace-aaa"</span><br/>
                      {')'}<br/>
                      <span style={{ color: 'var(--text-disabled)' }}>→ ProofReceipt {'{'} hash, type, position, ts {'}'}</span>
                    </div>
                  </div>
                  <div className="card" style={{ borderColor: 'var(--border)' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', fontFamily: 'var(--font-display)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
                      Verify
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      <span style={{ color: 'var(--cyan)' }}>VerifyProof</span>{'('}<br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>hash:</span> <span style={{ color: 'var(--green)' }}>"abc123..."</span><br/>
                      {'  '}<span style={{ color: 'var(--text-dim)' }}>type:</span> <span style={{ color: 'var(--green)' }}>"guardrail.pii_scan"</span><br/>
                      {')'}<br/>
                      <span style={{ color: 'var(--text-disabled)' }}>→ {'{'} valid, agent, source, corr_id, ts {'}'}</span><br/><br/>
                      <span style={{ color: 'var(--cyan)' }}>GetEntryByHash</span> <span style={{ color: 'var(--text-disabled)' }}>→ full content</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ACT 2 — CROSSING THE THRESHOLD: CHAINS */}
            {currentAct === 'chains' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="02" /> Crossing the Threshold</h3>
                <SectionContext lines={[
                  'Each source system forms its own independent SHA-256 hash chain. OpenShell events don\'t share a chain with Kagenti spans. Each chain is verifiable without trusting any other system.',
                  'This is what makes it different from a shared log: compromise one source and only that source\'s chain is affected. The other chains remain independently valid.',
                ]} />
                <StatsBar summary={summary} />
                <ChainView />
              </div>
            )}

            {/* ACT 3 — TESTS & ALLIES: TIMELINE */}
            {currentAct === 'timeline' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="03" /> Tests & Allies</h3>
                <SectionContext lines={[
                  'Three systems, three identities, three event formats — correlated by trace ID. When Kagenti records a tool call and OpenShell records the network decision for the same request, the correlation ID links them without either system knowing about the other.',
                  'No shared identity registry. No event format negotiation. The only agreement is a join key — a W3C trace ID, an X-Request-ID, or any string both systems propagate through their request headers.',
                ]} />
                <TimelineView />
              </div>
            )}

            {/* ACT 4 — THE TRANSFORMATION: PROOF RECEIPTS */}
            {currentAct === 'receipts' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="04" /> The Transformation</h3>
                <SectionContext lines={[
                  'The ledger doesn\'t just record what happened — it issues portable proof receipts. When AuthBridge runs a guardrail, the receipt travels with the request. Downstream services verify the proof instead of re-running the check.',
                  'Click through the flow to see how a single request accumulates verified proofs as it moves through the pipeline.',
                ]} />
                <ReceiptFlow />
              </div>
            )}

            {/* ACT 5 — THE ORDEAL: ADVERSARIAL */}
            {currentAct === 'ordeal' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="05" /> The Ordeal</h3>
                <SectionContext lines={[
                  '116 automated tests across 18 categories. SQL injection, write floods, forged entries, deleted rows, hash tampering, cross-chain contamination, replay attacks, and restart survival. Plus receipt-specific attacks: forged hashes, cross-type theft, content swaps, agent impersonation, correlation rebinding, and idempotency conflicts. All GREEN.',
                  'The database enforces append-only at the permission level — the application role cannot UPDATE or DELETE entries. The service verifies this at startup and refuses to run if the constraint is missing.',
                ]} />
                <VerifyView />
              </div>
            )}

            {/* ACT 5 — THE REWARD: CROSS-SYSTEM PROOF */}
            {currentAct === 'reward' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="06" /> The Reward</h3>
                <SectionContext lines={[
                  'Drift detection queries across sources to find authorization gaps — requests that were denied by the sandbox but never evaluated by the governance layer. Gaps that would be invisible to any single system.',
                  'This is the cross-system proof that no existing tool provides: correlation + verification + gap detection across independent agentic platforms.',
                ]} />
                <DriftView />
              </div>
            )}

            {/* ACT 6 — THE RETURN */}
            {currentAct === 'return' && (
              <div style={{ maxWidth: 700, margin: '0 auto' }}>
                <h3 style={{ marginBottom: 20 }}><SectionNum n="07" /> The Return</h3>

                <p style={{ color: 'var(--text-secondary)', fontSize: 16, lineHeight: 1.7, marginBottom: 24 }}>
                  Everything you just saw was live. Real entries from real systems —
                  OpenShell sandbox events, Kagenti OTEL traces, governance authority decisions —
                  chained, verified, and independently provable.
                </p>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--blue-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--blue)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    What the ledger proves — and what it doesn't
                  </div>
                  <ClosingPoint text="Proves: entries were not modified after submission. V2 canonical hash commits to all fields — content, agent, source, correlation, chain position, timestamp." />
                  <ClosingPoint text="Proves: proof receipts are tamper-evident. Swap the content, agent, or correlation ID and verification fails." />
                  <ClosingPoint text="Proves: cross-system events are correlatable by trace ID without shared identity." />
                  <ClosingPoint text="Does not prove: events are accurate when submitted. Attestation is the writer's responsibility. Receipts prove a claim was made, not that it's true. Integrity ≠ accuracy." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--cyan-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    Proof receipts — runtime trust propagation
                  </div>
                  <ClosingPoint text="IssueReceipt writes an entry and returns a compact ProofReceipt. The receipt travels as an HTTP header to the next service." />
                  <ClosingPoint text="VerifyProof validates the receipt by hash — returns the issuer, source, correlation, and content type. Fast (0.6ms p50). No need to re-run the check." />
                  <ClosingPoint text="GetEntryByHash retrieves full content when the verifier needs details. Two-step pattern: verify first (cheap), read content second (only if needed)." />
                  <ClosingPoint text="Eliminates redundant guardrails across multi-hop architectures. Each service checks once, proves it, and downstream trusts the proof." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--green-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    Why not QLDB, immudb, or a managed ledger?
                  </div>
                  <ClosingPoint text="Single-system immutable stores prove their own entries. They don't correlate across independent systems, issue portable proof receipts, or provide agent-aware adapters." />
                  <ClosingPoint text="This ledger adds: independent per-source chains, cross-system correlation, receipt issuance and verification, and adapters for OCSF and OTEL." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--purple-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--purple)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    The ecosystem gap
                  </div>
                  <ClosingPoint text="MCP standardizes agent-to-tool communication. OpenShell sandboxes agent execution. Kagenti orchestrates agent fleets. AGT provides per-framework governance gates." />
                  <ClosingPoint text="None of them provides a neutral, cross-system, cryptographically verifiable proof chain with portable receipts." />
                  <ClosingPoint text="We're seeking feedback on the verification model, the receipt primitive, and the integration pattern." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    Evidence depth
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
                    <EvidenceStat value="116" label="automated tests" />
                    <EvidenceStat value="18" label="test categories" />
                    <EvidenceStat value="10" label="security tests (injection, validation, permissions)" />
                    <EvidenceStat value="20" label="adversarial + receipt red team" />
                    <EvidenceStat value="2" label="live systems tested (OpenShell + Kagenti)" />
                    <EvidenceStat value="0" label="tests failing" />
                  </div>
                </div>

                <div style={{ textAlign: 'center', marginTop: 40, marginBottom: 20 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12, margin: '0 auto 16px',
                    background: 'linear-gradient(135deg, var(--blue), var(--purple))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 24,
                  }}>⛓</div>
                  <p style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>
                    Immutable Ledger — Apache-2.0 | Neutral infrastructure for agentic proof
                  </p>
                </div>
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom navigation */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '14px 32px', borderTop: '1px solid var(--border)', background: 'var(--surface-1)',
      }}>
        <button
          onClick={goBack}
          disabled={actIndex === 0}
          style={{
            padding: '8px 20px', borderRadius: 6, border: '1px solid var(--border)',
            background: 'transparent', color: actIndex === 0 ? 'var(--text-disabled)' : 'var(--text-secondary)',
            cursor: actIndex === 0 ? 'default' : 'pointer',
            fontWeight: 600, fontSize: 13, fontFamily: 'var(--font-display)',
          }}
        >
          Back
        </button>

        <span style={{ color: 'var(--text-disabled)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
          {actIndex + 1} / {ACTS.length}
        </span>

        {nextLabel && (
          <button
            onClick={goNext}
            style={{
              padding: '8px 24px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: 'linear-gradient(135deg, var(--blue), var(--purple))',
              color: '#fff', fontWeight: 700, fontSize: 13,
              fontFamily: 'var(--font-display)',
            }}
          >
            {nextLabel} →
          </button>
        )}
        {!nextLabel && <div style={{ width: 140 }} />}
      </div>
    </div>
  )
}

function SectionNum({ n }: { n: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 28, height: 28, borderRadius: '50%',
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      color: 'var(--text-dim)', fontSize: 12, fontWeight: 700,
      fontFamily: 'var(--font-display)', marginRight: 10,
    }}>{n}</span>
  )
}

function SectionContext({ lines }: { lines: string[] }) {
  return (
    <div style={{ marginBottom: 20 }}>
      {lines.map((line, i) => (
        <p key={i} style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, marginBottom: 6 }}>{line}</p>
      ))}
    </div>
  )
}

function StoryStep({ num, text }: { num: string; text: string }) {
  return (
    <div style={{ display: 'flex', gap: 14, marginBottom: 16, alignItems: 'flex-start' }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--surface-2)', border: '1px solid var(--border)',
        color: 'var(--text-dim)', fontSize: 13, fontWeight: 700,
        fontFamily: 'var(--font-display)',
      }}>{num}</div>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>{text}</p>
    </div>
  )
}

function ClosingPoint({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 10, alignItems: 'flex-start' }}>
      <span style={{ color: 'var(--text-disabled)', fontSize: 16, lineHeight: 1.4, flexShrink: 0 }}>—</span>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>{text}</p>
    </div>
  )
}

function EvidenceStat({ value, label }: { value: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
      <span style={{ fontSize: 22, fontWeight: 900, fontFamily: 'var(--font-display)',
        background: 'linear-gradient(135deg, var(--blue), var(--purple))',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
      }}>{value}</span>
      <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{label}</span>
    </div>
  )
}
