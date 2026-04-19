# Global Agent Instructions

## 1. The Workflow & Planning
* **Plan First:** Always analyze the request, propose a step-by-step plan, and wait for explicit confirmation before writing any code.
* **Atomic, Incremental Delivery:** Break large features down into small, independently testable milestones. Every step must result in a commit-ready state where the software builds successfully, tests pass, and the system is improved. Never propose a step that leaves the codebase broken.
* **Strict TDD:** Write failing unit tests for the planned changes first. Do not write implementation code until tests are defined and approved.
* **Immutable Tests:** Once a test is approved, you cannot modify it to make failing implementation code pass. Ask for permission if the test is flawed.
* **Test Coverage:** Include tests for both the "happy path" and expected "unhappy paths" (edge cases, errors). Isolate OS/system side effects using interface stubs (critical for system-level daemons or process manipulation).
* **Continuous Verification:** After every code modification and before proposing a commit, automatically run the project's available test suites, linters, and formatters. If everything passes, proceed to the next step silently. If any check fails, halt execution immediately, output the error log, and wait for guidance.
* **Stalled Progress Handling:** If multiple attempts fail, pause, summarize findings, propose hypotheses, and request direction before continuing.
* **Clarification First:** If requirements are ambiguous or incomplete, ask targeted questions before proposing a plan.
* **Pragmatism Over Perfection:** Prefer simple, maintainable solutions over overly abstract or premature optimizations.
* **Definition of Done:**
  A task is complete when:
  - Code compiles/builds
  - Tests (new and existing) pass
  - Edge cases are handled
  - Logging/observability is included where relevant
  - Documentation (if needed) is updated
* **Test-Driven Bug Fixing**: When a bug is reported, first analyze and document why the existing test suite failed to catch it (e.g., missing edge case, flawed mock, lack of integration coverage). Before writing any implementation code to fix the issue, you must write a failing test that reliably reproduces the bug. The bug is considered resolved only when this new test passes alongside the rest of the suite.
## 2. Code Philosophy
* **Standard Library First:** Always favor the language's standard library. Only write custom implementations for complex logic if no standard option exists.
* **Dependency Proposals:** If the standard library is insufficient, do not unilaterally select an external dependency. Propose 2-3 widely used, well-maintained community standards.
* **Dependency Analysis:** For each proposed dependency, provide a brief list of pros and cons (e.g., footprint size, maintenance status, ease of integration).
* **Dependency Approval:** Wait for explicit selection and approval before writing code that implements a new dependency.
* **Interface-Driven:** Design clear, decoupled interfaces to establish strict boundaries between system components.
* **Idiomatic & Context-Aware:** Match the existing coding style, naming conventions, and idiomatic patterns of the specific language (e.g., proper `Result` handling in Rust, idiomatic error checking in Go, or functional purity in Guile Scheme).

## 3. Agent Behavior
* **Surgical Changes:** Only modify code directly related to the active task. Never refactor unrelated surrounding code.
* **Robustness:** Never silently swallow errors. Implement explicit error propagation and handle edge cases gracefully.
* **Meaningful Docs:** Document the "why" behind complex architectural decisions or non-obvious logic, not the "what".

## 4. Version Control & History
* **Branch Naming:** All branches must follow the `<type>/<kebab-case-description>` convention (Valid types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`). Example: `feat/implement-priority-adjuster`.
* **Conventional Commits:** Every commit message must strictly follow the Conventional Commits format (`<type>(<optional scope>): <short, imperative description>`).
* **Commit Body:** Every commit must include a detailed body paragraph. The body must explain the context of the change, the reasoning behind the implementation, and any notable technical decisions made during the step. Do not just repeat the code changes in English.
