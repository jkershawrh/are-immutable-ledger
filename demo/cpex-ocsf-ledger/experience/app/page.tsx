'use client';

import { AnimatePresence, motion } from 'motion/react';
import Image from 'next/image';
import { useEffect, useMemo, useState } from 'react';
import { ProofFlow } from './components/ProofFlow';

type Mode = 'slides' | 'journey' | 'close';
type Perspective = 'business' | 'technical';

const businessSlides = [
  { kicker:'A BUSINESS STORY ABOUT AUTONOMOUS ACTION', title:'The $100 Agent', accent:'Give AI authority. Not unlimited trust.', body:'An operations agent can act at machine speed—inside a mandate the business can explain, enforce, and prove.', visual:'mandate' },
  { kicker:'THE ORDINARY WORLD', title:'At 2:13 AM, waiting is expensive.', accent:'The incident needs capacity now.', body:'A human approver is offline. The agent can solve the problem, but the company cannot hand it an open wallet.', visual:'clock' },
  { kicker:'THE CALL TO ADVENTURE', title:'Move fast without losing control.', accent:'Authorize the mission, not the machine.', body:'Alice delegates a narrow mandate: $100, approved vendors, spend scope, 30-minute expiry.', visual:'terms' },
  { kicker:'THE THRESHOLD', title:'Authority becomes executable policy.', accent:'Identity says who. Policy says whether. Evidence proves what happened.', body:'Three independent projects meet through open contracts—not shared implementation.', visual:'partners' },
  { kicker:'THE ORDEAL', title:'The agent asks for $30 more.', accent:'Only $15 remains.', body:'The policy engine stops the purchase before money moves. The denied attempt becomes signed evidence, not a missing log line.', visual:'deny' },
  { kicker:'THE ABYSS', title:'Then the policy plugin crashes.', accent:'The system fails closed.', body:'The panic becomes a terminal deny and still reaches the audit sink. Failure does not become permission.', visual:'panic' },
  { kicker:'THE RETURN', title:'Trust the proof, not the storyteller.', accent:'Every decision becomes portable evidence.', body:'Rev 3 is accepted end to end: six signatures, zero gaps, one dense stream across a real process restart, and a valid durable ledger chain.', visual:'proof' },
  { kicker:'THE LIVE JOURNEY', title:'Let’s watch the mandate work.', accent:'The business outcome first. The cryptography when it matters.', body:'Run the executive cut or step through the full evidence journey.', visual:'launch' },
];

const technicalSlides = [
  { kicker:'A TECHNICAL STORY ABOUT VERIFIABLE ENFORCEMENT', title:'Verdict to Proof', accent:'One finalized decision. Three open contracts.', body:'CPEX produces the DecisionLog today; the Praxis port will consume the same seam. The OCSF plugin signs the record, and the immutable ledger preserves independently verifiable evidence.', visual:'partners' },
  { kicker:'REQUEST INGRESS', title:'Identity and authority enter together.', accent:'agent-7 · run-4bf92f35 · signed $100 mandate', body:'The gateway carries agent identity, conversation correlation, request identity, scope, cap, and expiry into policy evaluation.', visual:'mandate' },
  { kicker:'POLICY EXECUTION', title:'CPEX finalizes the whole decision.', accent:'Allow, deny, deny_ignored, aborted—and panic.', body:'The audit seam receives the executor’s finalized DecisionLog, including suppressed denies that passive logging cannot reconstruct.', visual:'launch' },
  { kicker:'SIGNED RECORD', title:'The verdict becomes OCSF 6003.', accent:'Canonical bytes. Fingerprint. DSSE signature.', body:'AID-EMIT-1 defines covered bytes. Agent, run, request, chain, and stream stamps remain inside the signed event.', visual:'proof' },
  { kicker:'ADAPTER BOUNDARY', title:'The ledger preserves the same evidence.', accent:'No reinterpretation. No rewritten stamps.', body:'The CPEX adapter verifies covered bytes, detects gaps within each producer stream, and appends the record to the durable cpex.decision chain.', visual:'partners' },
  { kicker:'FAIL-CLOSED PATH', title:'A plugin actually panics.', accent:'catch_unwind → plugin_panic → terminal deny', body:'The executor contains the panic, records the violation, finalizes deny, and still hands the DecisionLog to the audit sink.', visual:'panic' },
  { kicker:'PROCESS RECOVERY', title:'Restart creates honest new identity.', accent:'New epoch. New chain_uid. stream_seq resets to 0.', body:'Density is checked within (epoch, stream_id); the ledger keeps its own continuity by entry_type. Nothing is forged to look continuous.', visual:'clock' },
  { kicker:'OFFLINE VERIFICATION', title:'Recompute everything.', accent:'Signatures, fingerprints, gaps, joins, and ledger chain.', body:'Rev 3 is accepted against CPEX 64c8eba: the real plugin_panic record reconciles with the other five on one host-named stream.', visual:'proof' },
];

const businessJourney = [
  { phase:'THE MENTOR’S GIFT', title:'Alice grants bounded authority', summary:'agent-7 receives a $100 emergency procurement mandate.', amount:0, balance:100, status:'AUTHORIZED', tone:'blue', detail:'Scope: spend · approved catalog only · TTL: 30 minutes', stream:'—', evidence:'Mandate signed' },
  { phase:'CROSSING THE THRESHOLD', title:'Purchase 01 · capacity credit', summary:'The agent buys $40 of approved emergency capacity.', amount:40, balance:60, status:'ALLOWED', tone:'green', detail:'Business scenario: mandate valid · vendor approved · $40 ≤ $100', stream:'gw-1:decision · seq 0', evidence:'Control shape: clean allow' },
  { phase:'TESTS AND ALLIES', title:'Purchase 02 · observability pack', summary:'A second $45 purchase is allowed. The running total reaches $85.', amount:45, balance:15, status:'ALLOWED', tone:'green', detail:'Business scenario: cumulative spend $85 · remaining authority $15', stream:'gw-1:decision · seq 1', evidence:'Control shape: modified allow' },
  { phase:'THE ORDEAL', title:'Purchase 03 · over the limit', summary:'The agent requests $30. Policy denies it before money moves.', amount:30, balance:15, status:'DENIED', tone:'red', detail:'Business scenario: requested total $115 · mandate cap $100', stream:'gw-1:decision · seq 2', evidence:'Control shape: policy deny' },
  { phase:'THE ABYSS', title:'The policy plugin panics', summary:'A real plugin panic is contained and becomes a terminal deny.', amount:0, balance:15, status:'FAIL-CLOSED', tone:'amber', detail:'catch_unwind → plugin_panic → finalized deny → audit sink', stream:'gw-1:decision · new epoch · seq 0', evidence:'Real path · Rev 3 accepted' },
  { phase:'DEATH AND REBIRTH', title:'The producer dies mid-stream', summary:'The process restarts. The new producer tells the truth about its new identity.', amount:0, balance:15, status:'RECOVERED', tone:'blue', detail:'One stream remains dense inside each epoch; no stamps are rewritten.', stream:'gw-1:decision · 2 epochs', evidence:'Accepted Rev 3 recovery path' },
  { phase:'THE REWARD', title:'The evidence converges', summary:'Identity and run correlation join every decision across producer lifecycles.', amount:0, balance:15, status:'CORRELATED', tone:'green', detail:'agent-7 and run-4bf92f35 on all 6 · request ID on Beat 05 only', stream:'1 stream · 2 epochs', evidence:'1 durable cpex.decision chain' },
  { phase:'RETURN WITH THE ELIXIR', title:'A third party verifies the truth', summary:'No gateway, plugin, or ledger operator must be trusted to tell the story.', amount:0, balance:15, status:'PROVEN', tone:'green', detail:'Rev 3: 6/6 signatures · 0 gaps · chain valid · offline verification', stream:'accepted Rev 3 bundle', evidence:'Real panic evidence included' },
];

const technicalJourney = [
  { phase:'INPUT CONTRACT', title:'Resolve signed context', summary:'All six records bind agent-7 and run-4bf92f35; the request join key appears on Beat 05 only.', amount:0, balance:100, status:'BOUND', tone:'blue', detail:'ai_agent.uid · metadata.correlation_uid · metadata.uid · request_id', stream:'gw-1:decision', evidence:'AID-EMIT-1 covered bytes' },
  { phase:'FINALIZED VERDICT', title:'Beat 01 · clean allow', summary:'Cedar and PII scan both allow; CPEX finalizes the complete DecisionLog.', amount:0, balance:100, status:'ALLOW', tone:'green', detail:'cedar-pdp: allowed · pii-scan: allowed', stream:'epoch 1755648000000000000 · seq 0', evidence:'Fingerprint + DSSE verify' },
  { phase:'TRANSFORM', title:'Beat 02 · modified allow', summary:'Policy allows while the transform phase records a payload modification.', amount:0, balance:100, status:'MODIFIED', tone:'green', detail:'cedar-pdp: allowed · pii-redactor: modified_payload', stream:'same epoch · seq 1', evidence:'Final verdict and steps signed' },
  { phase:'POLICY VIOLATION', title:'Beat 03 · terminal deny', summary:'Cedar denies the compensation request and the blocked result is still emitted.', amount:0, balance:100, status:'DENY', tone:'red', detail:'code=policy_denied · permission=read_compensation', stream:'same epoch · seq 2', evidence:'Denied record signed' },
  { phase:'SUPPRESSED DENY', title:'Beat 04 · deny_ignored + aborted', summary:'The finalized log preserves a suppressed transform deny and the branch it aborted.', amount:0, balance:100, status:'ALLOW', tone:'amber', detail:'injection-guard: deny_ignored · secondary-scan: aborted', stream:'same epoch · seq 3', evidence:'Invisible to passive logging' },
  { phase:'MANDATE DRAW', title:'Beat 05 · authorized effect', summary:'The mandate and Cedar checks allow; the signed request join key is retained on this record alone.', amount:0, balance:100, status:'ALLOW', tone:'green', detail:'mandate-check: allowed · cedar-pdp: allowed · request_id=corr-7f3e2a91', stream:'same epoch · seq 4', evidence:'Request-level join preserved' },
  { phase:'PANIC + RESTART', title:'Beat 06 · real plugin_panic', summary:'A new producer process drives a real panic through PluginManager and fails closed.', amount:0, balance:100, status:'DENY', tone:'red', detail:'minter: error · code=plugin_panic · new chain_uid', stream:'epoch 1755649000000000000 · seq 0', evidence:'Real path · DSSE verified' },
  { phase:'VERIFICATION', title:'Verify without either sink', summary:'The verifier recomputes canonical bytes, signatures, density, correlation, and ledger continuity.', amount:0, balance:100, status:'PASS', tone:'green', detail:'6 records · 6 signatures · 0 gaps · 1 valid cpex.decision chain', stream:'gw-1:decision · 2 epochs', evidence:'Rev 3 accepted end to end' },
];

const technicalMetrics = [
  ['CONTEXT','—','E1'], ['ALLOW','0','E1'], ['MODIFIED','1','E1'], ['DENY','2','E1'],
  ['DENY_IGNORED','3','E1'], ['ALLOW','4','E1'], ['PLUGIN_PANIC','0','E2'], ['PASS','6/6','2 EPOCHS'],
];

function Brands({ perspective, onPerspective }: { perspective: Perspective; onPerspective: (value: Perspective) => void }) {
  return <header className="brand-bar"><Image src="/logos/redhat.svg" width={138} height={46} alt="Red Hat" className="logo redhat"/><span className="brand-divider"/><Image src="/logos/ibm.png" width={84} height={34} alt="IBM" className="logo ibm"/><span className="brand-divider"/><span className="ai-brand"><Image src="/logos/ai-identity.svg" width={25} height={25} alt=""/>AI Identity</span><label className="perspective-select"><span>VIEW</span><select value={perspective} onChange={(event)=>onPerspective(event.target.value as Perspective)} aria-label="Choose demo perspective"><option value="business">Business story</option><option value="technical">Technical walkthrough</option></select></label><span className="demo-name">Verdict to Proof</span></header>;
}

function SlideVisual({ kind }: { kind:string }) {
  if (kind === 'clock') return <div className="big-visual"><span className="clock">02:13</span><small>INCIDENT ACTIVE · APPROVER OFFLINE</small></div>;
  if (kind === 'terms') return <div className="term-grid"><span><b>$100</b>Spend cap</span><span><b>30m</b>Time to live</span><span><b>1</b>Approved catalog</span></div>;
  if (kind === 'partners') return <div className="partner-stack"><span><b>01</b> AI Identity · authority</span><span><b>02</b> IBM CPEX / Praxis · policy</span><span><b>03</b> OCSF · portable evidence</span><span><b>04</b> Red Hat · durable proof</span></div>;
  if (kind === 'deny') return <div className="limit-visual"><div><span>$85</span><small>CONSUMED</small></div><i>+</i><div className="danger"><span>$30</span><small>REQUESTED</small></div><strong>DENIED</strong></div>;
  if (kind === 'panic') return <div className="panic-visual"><span>PLUGIN PANIC</span><motion.i animate={{ opacity:[.2,1,.2] }} transition={{ repeat:Infinity,duration:1.2 }}/><strong>DENY + EVIDENCE</strong></div>;
  if (kind === 'proof') return <div className="proof-stats"><span><b>6/6</b>signatures</span><span><b>0</b>gaps</span><span><b>1</b>valid chain</span></div>;
  if (kind === 'launch') return <div className="launch-visual"><span>ALLOW</span><span>OVER-LIMIT DENY</span><span>FAIL-CLOSED PANIC</span><strong>OFFLINE PROOF</strong></div>;
  return <MandateCard/>;
}

function MandateCard() {
  return <aside className="mandate-card"><div className="agent-orb">A7</div><div><p className="micro-label">DELEGATED AUTHORITY</p><h3>agent-7</h3></div><div className="mandate-amount">$100</div><dl><div><dt>Scope</dt><dd>Emergency procurement</dd></div><div><dt>Vendor</dt><dd>Approved catalog only</dd></div><div><dt>Expires</dt><dd>30 minutes</dd></div></dl><span className="signed-chip">Cryptographically signed</span></aside>;
}

export default function Home() {
  const [perspective,setPerspective] = useState<Perspective>('business');
  const [mode,setMode] = useState<Mode>('slides');
  const [slide,setSlide] = useState(0);
  const [step,setStep] = useState(0);
  const [auto,setAuto] = useState(false);
  const slides = perspective === 'business' ? businessSlides : technicalSlides;
  const journey = perspective === 'business' ? businessJourney : technicalJourney;
  const current = journey[step];
  const spent = useMemo(() => 100-current.balance,[current.balance]);
  const switchPerspective = (value: Perspective) => {
    setPerspective(value);
    setMode('slides');
    setSlide(0);
    setStep(0);
    setAuto(false);
  };

  useEffect(() => {
    if (!auto || mode !== 'journey') return;
    const timer = setTimeout(() => {
      if (step >= journey.length - 1) {
        setAuto(false);
        setMode('close');
        return;
      }
      const next = step + 1;
      setStep(next);
    }, 2600);
    return () => clearTimeout(timer);
  }, [auto, mode, step, journey.length]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight') {
        if (mode === 'slides') {
          if (slide < slides.length - 1) setSlide(slide + 1);
          else setMode('journey');
        } else {
          setStep(Math.min(journey.length - 1, step + 1));
        }
      }
      if (event.key === 'ArrowLeft') {
        if (mode === 'slides') setSlide(Math.max(0, slide - 1));
        else setStep(Math.max(0, step - 1));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mode, slide, step, slides.length, journey.length]);

  if (mode === 'slides') {
    const item=slides[slide];
    return <main className="stage"><Brands perspective={perspective} onPerspective={switchPerspective}/><div className="story-index">{slides.map((_,i)=><button key={i} className={i===slide?'active':''} onClick={()=>setSlide(i)} aria-label={`Go to slide ${i+1}`}/>)}</div><section className="hero-shell"><AnimatePresence mode="wait"><motion.div key={`${perspective}-${slide}`} className="hero-copy" initial={{opacity:0,y:28}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-18}} transition={{duration:.45}}><p className="eyebrow">{item.kicker}</p><h1>{item.title}</h1><h2>{item.accent}</h2><p className="lede">{item.body}</p></motion.div></AnimatePresence><motion.aside key={`${perspective}-${slide}-visual`} className="visual-shell" initial={{opacity:0,x:34}} animate={{opacity:1,x:0}} transition={{delay:.18,duration:.45}}><SlideVisual kind={item.visual}/></motion.aside></section><footer className="stage-footer"><button className="ghost" disabled={slide===0} onClick={()=>setSlide(Math.max(0,slide-1))}>← Back</button><span>{slide+1} / {slides.length}</span><button className="primary" onClick={()=>slide===slides.length-1?setMode('journey'):setSlide(slide+1)}>{slide===slides.length-1?'Enter the live journey':'Next →'}</button></footer></main>;
  }

  if (mode === 'close') {
    return <main className="stage close-stage"><Brands perspective={perspective} onPerspective={switchPerspective}/><section className="close-shell"><motion.div className="close-copy" initial={{opacity:0,y:24}} animate={{opacity:1,y:0}} transition={{duration:.55}}><p className="eyebrow">{perspective==='business'?'RETURN WITH THE ELIXIR':'VERIFICATION COMPLETE'}</p><h1>{perspective==='business'?<>Move at machine speed.<br/><span>Keep human accountability.</span></>:<>Enforce once.<br/><span>Verify everywhere.</span></>}</h1><p className="lede">{perspective==='business'?'The agent completed the mission inside a business mandate. Policy stopped what exceeded it. Failure denied safely. Independent proof survived the systems that produced it.':'The DecisionLog, signed OCSF event, producer stream, and ledger chain reconcile without trusting the gateway, plugin, sink, or exporter.'}</p><div className="close-outcomes"><span><b>{perspective==='business'?'MOVE':'FINALIZE'}</b>{perspective==='business'?'Autonomous action':'Complete DecisionLog'}</span><span><b>{perspective==='business'?'CONTROL':'SIGN'}</b>{perspective==='business'?'Bounded authority':'Canonical OCSF record'}</span><span><b>{perspective==='business'?'PROVE':'VERIFY'}</b>{perspective==='business'?'Portable evidence':'Offline and independent'}</span></div></motion.div><motion.aside className="close-mark" initial={{opacity:0,scale:.9}} animate={{opacity:1,scale:1}} transition={{delay:.2,duration:.55}}><div className="close-ring"><span>{perspective==='business'?'$100':'PASS'}</span><small>{perspective==='business'?<>MISSION<br/>COMPLETE</>:<>VERDICT<br/>TO PROOF</>}</small></div><p>AI Identity grants the mandate.<br/>IBM policy enforces it.<br/>Red Hat makes the evidence durable.</p></motion.aside></section><footer className="stage-footer close-footer"><span>THE $100 AGENT · VERDICT TO PROOF</span><button className="primary" onClick={()=>{setMode('slides');setSlide(0);setStep(0);setAuto(false)}}>Run again ↻</button></footer></main>;
  }

  return <main className="journey-stage"><Brands perspective={perspective} onPerspective={switchPerspective}/><div className="journey-progress">{journey.map((item,i)=><button key={item.phase} onClick={()=>{setStep(i);setAuto(false)}} className={i===step?'active':i<step?'done':''}><span>{String(i+1).padStart(2,'0')}</span>{item.phase}</button>)}</div>{perspective==='business'&&<div className="lens-note"><b>BUSINESS LENS</b> The procurement amounts translate Rev 3’s verified control behaviors into an executive scenario; choose Technical walkthrough for the exact signed record payloads.</div>}<section className="journey-grid"><div className="outcome-panel"><AnimatePresence mode="wait"><motion.div key={`${perspective}-${step}`} initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-12}}><p className="eyebrow">{current.phase}</p><div className={`status-pill ${current.tone}`}>{current.status}</div><h1>{current.title}</h1><p className="journey-summary">{current.summary}</p>{perspective==='business'?<><div className="transaction-card"><div><small>REQUEST</small><strong>{current.amount?`$${current.amount}`:'—'}</strong></div><div><small>SPENT</small><strong>${spent}</strong></div><div><small>REMAINING</small><strong className={current.balance<=15?'warn':''}>${current.balance}</strong></div></div><div className="spend-track"><motion.span animate={{width:`${spent}%`}} transition={{duration:.7}}/><i style={{left:'100%'}}>CAP</i></div></>:<div className="transaction-card technical-metrics"><div><small>RESULT</small><strong>{technicalMetrics[step][0]}</strong></div><div><small>STREAM_SEQ</small><strong>{technicalMetrics[step][1]}</strong></div><div><small>EPOCH</small><strong>{technicalMetrics[step][2]}</strong></div></div>}<p className="decision-detail">{current.detail}</p><div className="evidence-row"><span><small>PRODUCER</small>{current.stream}</span><span><small>EVIDENCE</small>{current.evidence}</span></div></motion.div></AnimatePresence></div><div className="proof-panel"><ProofFlow activeIndex={step} perspective={perspective}/><div className="proof-caption"><span>{perspective==='business'?'BUSINESS JOIN':'SIGNED JOIN KEYS'}</span><b>agent-7</b><i>+</i><b>run-4bf92f35</b><small>Identity and conversation survive process and stream boundaries.</small></div></div></section><footer className="journey-footer"><button className="ghost" onClick={()=>{setMode('slides');setSlide(slides.length-1);setAuto(false)}}>← Presentation</button><div className="journey-controls"><button className="ghost" disabled={step===0} onClick={()=>{setStep(Math.max(0,step-1));setAuto(false)}}>Back</button><span>{step+1} / {journey.length}</span><button className={auto?'pause':'primary'} onClick={()=>setAuto(!auto)}>{auto?'Pause':'Run story'}</button><button className="primary" onClick={()=>{if(step===journey.length-1)setMode('close');else setStep(step+1);setAuto(false)}}>{step===journey.length-1?'Close →':'Next →'}</button></div></footer></main>;
}
