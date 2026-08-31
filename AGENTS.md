# AGENTS.md

Engineering principles distilled from a reference library.
Applies to every project unless a project-level `CLAUDE.md` overrides it.

**These are default design constraints, not commandments.** Apply them unless
project context gives a stronger reason not to. When departing from one in a way
that materially affects architecture, reliability, security, or
maintainability, say so and record why.

**Do not introduce architectural ceremony merely to satisfy a rule in this
file.** Prefer the simplest design that meets current requirements and keeps the
relevant boundary changeable later. A rule producing indirection without a
concrete payoff is being misapplied.

**Software engineering is programming integrated over time.** [Winters et al.]
The question behind most rules here is not "does it work?" but "can this still
be changed in three years?"

Each rule is tagged:

- **MUST** — not doing this introduces a defect or a risk. Departing from it
  requires saying so explicitly.
- **DEFAULT** — usually the better option. Departing is fine with a reason.
- **JUDGE** — context decides. Think before choosing, and record the choice.

Bracketed names mark the source, so a rule can be argued with knowingly rather
than by accident.

---

## 0. Core rules

The ones that come up most often. Obligation level is carried by the tag, not by
position in this section.

1. **MUST — Do not claim a test, benchmark, security property, compatibility
   guarantee, or operational behavior that was not actually verified.** State
   what was run and what was not. "Should work" is not a result, and neither is
   a test that was written but never executed.
2. **MUST — Measure before claiming a performance change.** No performance claim
   without a number from the real system. Averages hide the problem; the tail is
   what users experience. [Sites]
3. **MUST — Stop and ask rather than guess** when the requirement is ambiguous
   in a way that changes the design, when the operation is destructive or
   irreversible, when production data or credentials are involved, or when a
   **JUDGE** decision has no answer available from context. One round trip costs
   less than a confident wrong assumption.
4. **DEFAULT — If it is hard to test, it is badly designed.** Difficulty writing
   the test is information about the design, not an obstacle to route around.
   [Freeman & Pryce]
5. **DEFAULT — No abstraction without a second real implementation in sight.**
   Speculative abstraction costs more than duplication. [GoF, read against its
   own reputation]

---

## 1. Design and coupling

- **JUDGE — Coupling is not bad in itself.** It becomes a problem when high
  **integration strength**, large **distance**, and high **volatility** of the
  contract combine. Evaluate all three before calling something "coupled," and
  before adding an interface to "fix" it. [Khononov]
- **DEFAULT** — Couple tightly what changes together and sits close. Couple
  loosely what is far apart or changes at a different rate.
- **DEFAULT** — Program to an interface where the implementation genuinely
  varies. Prefer composition over inheritance. Encapsulate what varies. [GoF]
- **MUST** — Do not apply a GoF pattern by name. If the choice does not fit in
  one sentence naming what varies and why, the pattern is not needed.
- **DEFAULT — Tell, don't ask**: ask an object to do something rather than
  pulling its state out to decide elsewhere. [Freeman & Pryce]
- **JUDGE** — Business logic should not depend on infrastructure details *when
  the boundary has a clear payoff* (swappable backend, testability under load,
  independent deployment). For a small tool or a one-off script, ports and
  adapters are usually net negative.
- **MUST — Hyrum's Law**: with enough users, every observable behavior becomes a
  contract, documented or not. Treat log format, error strings and codes, result
  ordering, timing, headers, and default values as potential contracts whenever
  a consumer can observe them. [Winters et al.]

## 2. Testing

- **DEFAULT** — Red, green, refactor. Small steps, failing assertion first.
  [Beck]
- **DEFAULT** — Start with a **walking skeleton**: the thinnest end-to-end path,
  deployed and automated, before building inward. [Freeman & Pryce]
- **JUDGE — Mocks vs. real collaborators.** Mock **roles** at boundaries you
  own; prefer real objects inside the domain. If a third-party library must be
  faked, wrap it in an owned interface first. Over-mocking produces tests that
  pass while the system is broken. [Freeman & Pryce]
- **MUST — The Beyoncé Rule**: if a behavior matters, a test must fail when it
  breaks. [Winters et al.]
- **MUST** — Test behavior, not implementation. A refactor that preserves
  behavior must not break tests.
- **DEFAULT** — Name the test after the behavior, not the method under call.

## 3. Data and distributed systems

- **MUST** — Networks fail, partition, reorder, and duplicate. Clocks on
  different machines are not comparable. Any design assuming otherwise is wrong.
  [Kleppmann]
- **MUST — At-least-once delivery requires idempotent effects or explicit
  deduplication.** Natural idempotency, conditional writes, and idempotency keys
  are all valid; silently assuming exactly-once is not.
- **MUST — Before introducing distributed state, record:** required consistency,
  failure mode, acceptable staleness, recovery strategy. "Eventual" is a
  constraint with observable consequences, not a shrug.
- **MUST — Any serialized format that outlives the process writing it has a
  stated compatibility policy.** Formats crossing a version, storage, or service
  boundary need forward and backward compatibility; a cache deliberately
  invalidated on every release needs only a version marker that forces the
  invalidation. Preserve field identity and meaning unless a versioned migration
  says otherwise.
- **JUDGE** — Name which of reliability, scalability, or maintainability is
  being prioritized in any architectural decision. They trade against each
  other. [Kleppmann]

## 4. Performance

- **MUST — Before claiming a performance improvement, record:** workload,
  environment, baseline, percentile, measurement method. Without these the claim
  is not a claim. [Sites]
- **MUST** — Instrument before assuming. Intuition about where time goes is
  wrong with surprising frequency.
- **DEFAULT** — Four fundamental resources: **CPU, memory, disk, network**. Rule
  out saturation, interference, and waiting on each in order before touching
  code.
- **DEFAULT** — Chase individual slow cases, not the mean. A histogram or
  per-request trace beats any aggregate metric.
- **DEFAULT** — Usual tail-latency causes: lock contention, GC pauses, cache
  misses, I/O queueing, noisy neighbors. Check these before rewriting anything.
  [Koopman, OSTEP]

## 5. Operating system and concurrency

- **MUST — Nothing is durable before the durability call returns, and the call
  returning is not always enough.** `fsync` on a file does not make a new
  directory entry durable; the parent directory needs its own sync. Know whether
  the platform gives `fsync`, `fdatasync`, or neither, and treat crash
  consistency as a design problem rather than a detail. [Arpaci-Dusseau]
- **MUST — Shared mutable state across threads has an explicit synchronization
  discipline:** which mechanism protects which invariant, and where locks are
  involved, in what order they are acquired. Channels, atomics, and lock-free
  structures all qualify as mechanisms; absence of a stated one does not.
- **DEFAULT** — Prefer message passing at process and task boundaries. Shared
  state inside a well-scoped concurrent structure is fine when the discipline
  above is explicit.
- **MUST** — Race conditions are designed out, not debugged out.

## 6. Security and reliability

- **MUST — Least privilege.** No process, credential, or service gets more
  permission than its immediate task requires. [Adkins et al.]
- **MUST — Validate all external input at the edge against the narrowest
  positive specification available:** type, range, schema, grammar, or
  allowlist. Do not rely on rejecting known-bad values.
- **MUST** — Design for recovery from the start: how to roll back, how to rotate
  a compromised credential, how to rebuild state.
- **JUDGE — Fail secure vs. fail available**, chosen per component, not left to
  whatever the error handling happens to do.
- **DEFAULT** — Define the **blast radius** of each component: if this is
  compromised, what does the attacker reach? Compartmentalize to shrink it.
- **JUDGE** — Security and reliability sometimes pull opposite ways. Name the
  conflict instead of resolving it by reflex.

## 7. Networking and I/O

- **MUST — Every network call has an explicit timeout.** Never the library
  default.
- **MUST — Retries require a defined idempotency policy first**, then
  exponential backoff, jitter, and a retry ceiling. A non-idempotent operation
  is not retried until its effect is made safe to repeat. Retrying blindly on
  timeout is how duplicate charges happen.
- **MUST** — Retries without jitter synchronize clients and amplify the outage.
- **DEFAULT** — Application-layer timeouts shorter than transport-layer ones,
  not the reverse.
- **DEFAULT** — When behavior is inexplicable, capture the traffic before
  theorizing. Handshake, `TIME_WAIT`, keepalive, MTU and fragmentation are where
  most "mysterious hangs" live. [Fall & Stevens]

## 8. Sustainability over time

- **DEFAULT** — If something must change in a hundred places, write the tool.
  Automated large-scale change beats manual migration. [Winters et al.]
- **MUST — Deprecate with a plan**: nothing is marked obsolete without a
  migration path and a date.
- **DEFAULT** — Record architectural decisions when made, with context and
  rejected alternatives. Six months later nobody remembers why.
- **DEFAULT** — Prefer boring and proven over novel, absent a concrete written
  reason.

---

## 9. Known tensions between these sources

These books do not agree. When they collide, choose explicitly:

- **Classicist vs. outside-in TDD.** Beck works inside-out with real state;
  Freeman and Pryce work outside-in with role mocks. The second designs
  boundaries better; the first produces tests that survive refactoring. Choose
  by whether the problem is one of integration or of algorithm.
- **GoF vs. current practice.** The catalog assumes the deep class hierarchies
  of the nineties. The core ideas hold; several concrete patterns are noise in
  languages with first-class functions or traits.
- **Decoupling vs. simplicity.** Khononov is the explicit corrective to the
  reflex of decoupling everything. Unnecessarily loose coupling costs
  indirection and makes the system harder to reason about.
- **Security vs. availability.** Adkins et al. treat this as a permanent design
  tension, not a problem with one answer.

---

## Sources

Arpaci-Dusseau, *Operating Systems: Three Easy Pieces* · Kleppmann, *Designing
Data-Intensive Applications* · Sites, *Understanding Software Dynamics* ·
Winters, Manshreck & Wright, *Software Engineering at Google* · Adkins et al.,
*Building Secure and Reliable Systems* · Freeman & Pryce, *Growing
Object-Oriented Software, Guided by Tests* · Koopman, *Stack Computers* · Beck,
*Test-Driven Development by Example* · Khononov, *Balancing Coupling in Software
Design* · Gamma, Helm, Johnson & Vlissides, *Design Patterns* · Fall & Stevens,
*TCP/IP Illustrated, Volume 1*
