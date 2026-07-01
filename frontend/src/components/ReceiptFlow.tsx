import { motion } from 'motion/react'
import { useState } from 'react'

const HOPS = [
  {
    id: 'authbridge',
    label: 'AuthBridge',
    sub: 'Guardrail proxy',
    color: 'var(--cyan)',
    action: 'Runs PII scan guardrail',
    receipt: 'guardrail.pii_scan → clean',
    x: 60,
  },
  {
    id: 'gateway',
    label: 'MCP Gateway',
    sub: 'Route + policy',
    color: 'var(--purple)',
    action: 'Verifies receipt, skips re-scan',
    receipt: 'gateway.routing → mcp-server-1',
    x: 330,
  },
  {
    id: 'server',
    label: 'MCP Server',
    sub: 'Tool execution',
    color: 'var(--green)',
    action: 'Verifies both receipts, executes tool',
    receipt: 'tool.executed → search',
    x: 600,
  },
]

export function ReceiptFlow() {
  const [step, setStep] = useState(0)
  const maxSteps = 7

  const advance = () => setStep(s => Math.min(s + 1, maxSteps))
  const reset = () => setStep(0)

  return (
    <div>
      <div className="card" style={{ padding: 32, marginBottom: 16 }}>
        <svg width="100%" viewBox="0 0 860 340" style={{ maxWidth: 860 }}>
          {/* Ledger at bottom */}
          <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
            <rect x={230} y={260} width={400} height={60} rx={12}
              fill="var(--surface-2)" stroke="url(#receipt-gradient)" strokeWidth={2} />
            <defs>
              <linearGradient id="receipt-gradient" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="var(--blue)" />
                <stop offset="100%" stopColor="var(--purple)" />
              </linearGradient>
            </defs>
            <text x={430} y={288} textAnchor="middle" fill="var(--text-primary)" fontSize={14}
              fontFamily="var(--font-display)" fontWeight={900}>Immutable Ledger</text>
            <text x={430} y={306} textAnchor="middle" fill="var(--text-dim)" fontSize={10}
              fontFamily="var(--font-mono)">IssueReceipt · VerifyProof · GetEntryByHash</text>
          </motion.g>

          {/* Service boxes */}
          {HOPS.map((hop, i) => (
            <motion.g key={hop.id}
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.15 }}
            >
              <rect x={hop.x} y={30} width={200} height={70} rx={10}
                fill="var(--surface-2)"
                stroke={step >= i * 2 + 1 ? hop.color : 'var(--border)'}
                strokeWidth={step >= i * 2 + 1 ? 2 : 1} />
              <text x={hop.x + 100} y={55} textAnchor="middle" fill="var(--text-primary)"
                fontSize={14} fontFamily="var(--font-display)" fontWeight={700}>{hop.label}</text>
              <text x={hop.x + 100} y={75} textAnchor="middle" fill="var(--text-dim)"
                fontSize={10} fontFamily="var(--font-mono)">{hop.sub}</text>
            </motion.g>
          ))}

          {/* Step 1: AuthBridge writes to ledger */}
          {step >= 1 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={160} y1={100} x2={330} y2={260}
                stroke="var(--cyan)" strokeWidth={1.5} strokeDasharray="4 4"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5 }} />
              <text x={220} y={180} fill="var(--cyan)" fontSize={9} fontFamily="var(--font-mono)"
                transform="rotate(-35, 220, 180)">IssueReceipt</text>
            </motion.g>
          )}

          {/* Step 2: Receipt comes back */}
          {step >= 2 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={340} y1={260} x2={170} y2={100}
                stroke="var(--cyan)" strokeWidth={1.5} strokeDasharray="2 2"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4 }} />
              <motion.rect x={85} y={108} width={150} height={28} rx={6}
                fill="var(--cyan)" fillOpacity={0.1} stroke="var(--cyan)" strokeWidth={1}
                initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }} />
              <text x={160} y={126} textAnchor="middle" fill="var(--cyan)" fontSize={9}
                fontFamily="var(--font-mono)">ProofReceipt ✓</text>
            </motion.g>
          )}

          {/* Step 3: Receipt header travels to Gateway */}
          {step >= 3 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={260} y1={65} x2={330} y2={65}
                stroke="var(--text-dim)" strokeWidth={2}
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4 }} />
              <motion.rect x={270} y={138} width={170} height={22} rx={4}
                fill="var(--surface-3)" stroke="var(--border)" strokeWidth={1}
                initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} />
              <text x={355} y={153} textAnchor="middle" fill="var(--text-dim)" fontSize={8}
                fontFamily="var(--font-mono)">X-Proof-Receipt: eyJo...</text>
            </motion.g>
          )}

          {/* Step 4: Gateway verifies */}
          {step >= 4 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={430} y1={100} x2={430} y2={260}
                stroke="var(--purple)" strokeWidth={1.5} strokeDasharray="4 4"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4 }} />
              <text x={445} y={185} fill="var(--purple)" fontSize={9} fontFamily="var(--font-mono)">VerifyProof</text>
              <motion.circle cx={435} cy={195} r={12} fill="var(--green)" fillOpacity={0.15}
                stroke="var(--green)" strokeWidth={1}
                initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.3, type: 'spring' }} />
              <text x={435} y={199} textAnchor="middle" fill="var(--green)" fontSize={10}>✓</text>
            </motion.g>
          )}

          {/* Step 5: Gateway issues its own receipt + forwards */}
          {step >= 5 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={530} y1={65} x2={600} y2={65}
                stroke="var(--text-dim)" strokeWidth={2}
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4 }} />
              <motion.rect x={540} y={138} width={190} height={22} rx={4}
                fill="var(--surface-3)" stroke="var(--border)" strokeWidth={1}
                initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} />
              <text x={635} y={153} textAnchor="middle" fill="var(--text-dim)" fontSize={8}
                fontFamily="var(--font-mono)">X-Proof-Receipt: 2 receipts</text>
            </motion.g>
          )}

          {/* Step 6: Server verifies both */}
          {step >= 6 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.line x1={700} y1={100} x2={550} y2={260}
                stroke="var(--green)" strokeWidth={1.5} strokeDasharray="4 4"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4 }} />
              <text x={645} y={185} fill="var(--green)" fontSize={9} fontFamily="var(--font-mono)"
                transform="rotate(35, 645, 185)">VerifyProof ×2</text>
              <motion.circle cx={660} cy={210} r={12} fill="var(--green)" fillOpacity={0.15}
                stroke="var(--green)" strokeWidth={1}
                initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.3, type: 'spring' }} />
              <text x={660} y={214} textAnchor="middle" fill="var(--green)" fontSize={10}>✓✓</text>
            </motion.g>
          )}

          {/* Step 7: All three in ledger */}
          {step >= 7 && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {[310, 430, 550].map((cx, i) => (
                <motion.circle key={i} cx={cx} cy={290} r={5}
                  fill={['var(--cyan)', 'var(--purple)', 'var(--green)'][i]}
                  initial={{ scale: 0 }} animate={{ scale: [0, 1.5, 1] }}
                  transition={{ delay: i * 0.15, type: 'spring' }} />
              ))}
              <text x={430} y={335} textAnchor="middle" fill="var(--text-secondary)" fontSize={11}
                fontFamily="var(--font-display)" fontWeight={600}>
                3 receipts · 3 sources · 1 correlation · all verifiable
              </text>
            </motion.g>
          )}
        </svg>
      </div>

      {/* Step controls + narrative */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          {step === 0 && <StepNarrative title="Request arrives" text="A request enters the agentic pipeline. It will pass through three services. Today, each service re-runs the same guardrail checks independently. With receipts, each check runs once." />}
          {step === 1 && <StepNarrative title="AuthBridge issues receipt" text="AuthBridge runs the PII scan guardrail. Instead of just allowing the request, it calls IssueReceipt — writing the guardrail result to the ledger and getting back a ProofReceipt with the entry hash." color="var(--cyan)" />}
          {step === 2 && <StepNarrative title="Receipt returned" text="The ProofReceipt contains the entry_hash, entry_type, chain_position, and timestamp. AuthBridge encodes it as a compact base64 header." color="var(--cyan)" />}
          {step === 3 && <StepNarrative title="Receipt travels with request" text="The X-Proof-Receipt header carries the proof to the next hop. The MCP Gateway receives the request with the receipt attached — no out-of-band communication needed." />}
          {step === 4 && <StepNarrative title="Gateway verifies, skips re-check" text="The MCP Gateway calls VerifyProof with the hash. The ledger confirms: valid, issued by authbridge-proxy, 0.6ms ago, for this correlation ID. The gateway skips running the PII scan again." color="var(--purple)" />}
          {step === 5 && <StepNarrative title="Gateway adds its own receipt" text="The gateway issues its own receipt for the routing decision, then forwards both receipts to the MCP Server. The request now carries proof of two checks." color="var(--purple)" />}
          {step === 6 && <StepNarrative title="Server verifies both receipts" text="The MCP Server verifies both receipts in parallel. Two VerifyProof calls, ~0.6ms each. It now knows: PII scan passed (AuthBridge) and routing was approved (Gateway) — without running either check." color="var(--green)" />}
          {step === 7 && <StepNarrative title="Full chain of trust in the ledger" text="Three receipts from three services, linked by the same correlation ID. Each independently verifiable. Each hash-chained. The auditor can reconstruct the entire decision path from one query." />}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button onClick={advance} disabled={step >= maxSteps} className="nav-btn" style={{
            background: step >= maxSteps ? 'var(--surface-2)' : 'var(--blue-bg)',
            borderColor: 'var(--blue-border)', color: step >= maxSteps ? 'var(--text-disabled)' : 'var(--blue)',
            minWidth: 120,
          }}>
            {step === 0 ? 'Start flow' : step >= maxSteps ? 'Complete' : `Step ${step + 1} →`}
          </button>
          {step > 0 && (
            <button onClick={reset} className="nav-btn" style={{ minWidth: 120 }}>
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function StepNarrative({ title, text, color }: { title: string; text: string; color?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
      style={{ borderColor: color ? `${color}30` : 'var(--border)', borderLeft: color ? `3px solid ${color}` : undefined }}
    >
      <div style={{ fontSize: 14, fontWeight: 700, color: color || 'var(--text-primary)', fontFamily: 'var(--font-display)', marginBottom: 6 }}>
        {title}
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>{text}</p>
    </motion.div>
  )
}
