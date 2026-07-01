import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Header } from './components/Header'
import { SystemDiagram } from './components/SystemDiagram'
import { ChainView } from './components/ChainView'
import { TimelineView } from './components/TimelineView'
import { VerifyView } from './components/VerifyView'
import { DriftView } from './components/DriftView'
import { StatsBar } from './components/StatsBar'
import { useFetch } from './hooks/useLedger'
import { api } from './api/ledgerApi'

const ACTS = ['story', 'architecture', 'chains', 'timeline', 'ordeal', 'reward', 'return'] as const
type Act = typeof ACTS[number]

const NEXT_LABELS: Record<Act, string> = {
  story: 'See the architecture',
  architecture: 'Explore the chains',
  chains: 'View the timeline',
  timeline: 'Face the ordeal',
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
          universal proof chain for agentic systems
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
                  Every agentic system logs what happened. None of them can prove it.
                </p>
                <div style={{ maxWidth: 700 }}>
                  <StoryStep num="1" text="OpenShell sandboxes agents and logs OCSF security events — network allows, denials, process launches. The logs go to JSONL files. They can be edited. They can be deleted." />
                  <StoryStep num="2" text="Kagenti orchestrates agent fleets and captures OTEL traces — tool calls, LLM requests, agent lifecycle. The traces go to Phoenix or Jaeger. They can be overwritten." />
                  <StoryStep num="3" text="Governance systems evaluate authority — passports, scoped permissions, policy decisions. The decisions are checked but not chained. There's no proof they weren't altered after the fact." />
                  <StoryStep num="4" text="When compliance asks 'show me verifiable proof of what this agent did across all three systems' — nobody has an answer. Observability is not proof. Logs are not evidence. That's the ordinary world." />
                </div>
              </div>
            )}

            {/* ACT 1 — THE CALL: ARCHITECTURE */}
            {currentAct === 'architecture' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="01" /> The Call to Adventure</h3>
                <SectionContext lines={[
                  'What if every system wrote its events — in its own format, with its own identity — to a single chain that nobody owns?',
                  'The ledger doesn\'t interpret content. It chains raw bytes, stores metadata, and makes everything independently verifiable. One gRPC call. Your data. Chained and proven.',
                ]} />
                <SystemDiagram />
              </div>
            )}

            {/* ACT 2 — CROSSING THE THRESHOLD: CHAINS */}
            {currentAct === 'chains' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="02" /> Crossing the Threshold</h3>
                <SectionContext lines={[
                  'Each source system writes entries that form independent SHA-256 hash chains. Each chain is self-contained — verifiable without trusting any other system.',
                  'Click any chain to see the linked blocks: entry hash, previous hash, chain position. Every link is cryptographically bound to the one before it.',
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
                  'Three systems, three identities, three event formats — united by correlation IDs. When OpenShell denies a request and Kagenti records the tool call, the same trace ID links them.',
                  'No shared identity registry. No format standardization. Just a join key that each system already has.',
                ]} />
                <TimelineView />
              </div>
            )}

            {/* ACT 4 — THE ORDEAL: ADVERSARIAL */}
            {currentAct === 'ordeal' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="04" /> The Ordeal</h3>
                <SectionContext lines={[
                  'The chains have been tested against every attack we could throw at them. SQL injection, write floods, forged entries, deleted rows, hash tampering, cross-chain contamination.',
                  'Click Verify All to watch each chain pass cryptographic verification in real time.',
                ]} />
                <VerifyView />
              </div>
            )}

            {/* ACT 5 — THE REWARD: CROSS-SYSTEM PROOF */}
            {currentAct === 'reward' && (
              <div>
                <h3 style={{ marginBottom: 8 }}><SectionNum n="05" /> The Reward</h3>
                <SectionContext lines={[
                  'The reward is what no single system could provide alone: a unified, verifiable proof chain across independent agentic systems.',
                  'Drift detection finds authorization gaps — requests that were denied by the sandbox but never evaluated by the governance layer. Gaps that would be invisible without cross-system correlation.',
                ]} />
                <DriftView />
              </div>
            )}

            {/* ACT 6 — THE RETURN */}
            {currentAct === 'return' && (
              <div style={{ maxWidth: 700, margin: '0 auto' }}>
                <h3 style={{ marginBottom: 20 }}><SectionNum n="06" /> The Return</h3>

                <p style={{ color: 'var(--text-secondary)', fontSize: 16, lineHeight: 1.7, marginBottom: 24 }}>
                  Everything you just saw was live. Real entries from real systems —
                  OpenShell sandbox events, Kagenti OTEL traces, governance authority decisions —
                  all chained, all verified, all independently provable.
                </p>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--blue-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--blue)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    What the ledger proves
                  </div>
                  <ClosingPoint text="Every event is hash-chained and tamper-evident. Modify one byte and the chain breaks." />
                  <ClosingPoint text="Cross-system correlation by trace ID — no shared identity, no format coupling." />
                  <ClosingPoint text="Authorization gaps are detectable across system boundaries — drift that no single system could find alone." />
                  <ClosingPoint text="92 automated tests: functional, security, adversarial, synthetic, live integration. All GREEN." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--green-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    The universal contract
                  </div>
                  <ClosingPoint text="One gRPC call. Your identity. Your event format. Chained and verifiable." />
                  <ClosingPoint text="No shared identity registry required. No event format standardization." />
                  <ClosingPoint text="Any agentic system plugs in. OpenShell, Kagenti, ARE, or the 30-line Python script you write in 5 minutes." />
                </div>

                <div className="card" style={{ marginBottom: 24, borderColor: 'var(--purple-border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--purple)', fontFamily: 'var(--font-display)', marginBottom: 16 }}>
                    What's missing from the ecosystem
                  </div>
                  <ClosingPoint text="MCP gives agents protocols. OpenShell gives agents sandboxes. Kagenti gives agents orchestration. AGT gives agents per-framework governance." />
                  <ClosingPoint text="None of them gives the ecosystem a shared, neutral, cryptographically verifiable proof chain." />
                  <ClosingPoint text="This is that layer." />
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
