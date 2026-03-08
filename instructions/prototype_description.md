You are a senior AI product engineer and systems architect.

Your task is to design and implement a working prototype of an AI content orchestration platform for persona-based social content generation.

Do not treat this as a fixed architecture spec. Treat it as a target workflow and realize it in the most practical, working way possible.

You have freedom in implementation details, framework choices, service boundaries, and orchestration patterns, as long as the final system preserves the intended behavior.

## Product goal

Build a prototype where AI agents:
1. parse trends from social platforms,
2. plan content per platform,
3. orchestrate content generation through ComfyUI workflows,
4. send generated assets for approval through Telegram,
5. publish approved assets to target platforms.

The system should be modular, extensible, and prototype-friendly.
The priority is working end-to-end behavior, not perfect production architecture.

---

## High-level workflow to realize

### 1. Trends ingestion
There should be a `Trends Parser` layer that gathers and summarizes trend signals from:
- TikTok
- Instagram
- X.com

This parser should extract useful content signals such as:
- trending topics
- video styles
- visual formats
- captions/hooks
- music or audio patterns where relevant
- repeated post structures
- viral content ideas

It does not have to be perfect.
For prototype purposes, it may use:
- APIs where available
- scraping where appropriate
- mock adapters
- manually seeded data
- simulated trend inputs

The implementation choice is up to you, but the system should be built so this layer can be improved later.

### 2. Planning agent
There should be a `Planning Agent` that receives trend summaries and transforms them into structured platform-specific content directions.

It should:
- interpret trend summaries
- identify promising content opportunities
- split planning by platform
- produce structured instructions for downstream content agents

### 3. Platform-specific planning agents
There should be platform-aware planning agents, such as:
- TikTok Content Planning Agent
- Instagram Content Planning Agent
- X.com Agent

These agents should convert trends into concrete content plans.

Each plan may include:
- idea
- platform objective
- content type
- caption direction
- prompt direction
- visual reference direction
- video/photo generation requirements
- persona usage instructions
- optional music/topic/style cues
- any metadata needed for downstream generation

These agents do not need to be identical.
Let them behave differently per platform if that improves output quality.

### 4. Workflow agent
There should be a `Workflow Agent` that receives platform plans and turns them into executable generation steps.

Its job is to:
- select the right generation workflow
- run content creation one item at a time
- coordinate ComfyUI-based jobs
- collect outputs
- handle retries/failures
- decide what asset package is ready for review

This agent is the orchestration center.

### 5. ComfyUI workflow execution
There should be a ComfyUI execution layer with support for workflows such as:
- animation / video generation
- face swap / identity transfer
- image generation
- any other relevant workflows

The exact workflows may differ, but the prototype should be designed so these are plug-in modules.

The diagram references examples like:
- Wan2.2 animate
- Face Swap
- Nano Banana

Treat these as representative workflow types, not hardcoded requirements.
You may rename, replace, or abstract them if needed.

### 6. Telegram approval loop
All generated outputs should be sent to Telegram for approval.

Telegram should act as the human-in-the-loop review layer.

Approval flow should support at least:
- preview generated asset
- approve
- reject
- optionally request regeneration

If content is rejected, it should loop back into the workflow system for re-generation or correction.

If content is approved, it moves to publishing.

### 7. Publishing layer
Approved content should be routed to target platforms:
- TikTok
- Instagram
- X.com

For the prototype, publishing may be:
- real API publishing where feasible
- mock publishing
- draft creation
- export-ready packaging

You may choose the most practical approach per platform.
Do not fake official support.
If platform APIs are restricted, implement the best realistic prototype alternative.

---

## Important design principle

Leave room for agentic freedom.

Do not over-constrain the system into brittle hardcoded logic.
Use a mix of:
- deterministic workflows
- LLM-based planning
- modular adapters
- configurable pipelines

Use the minimum amount of complexity needed to make the prototype coherent and extensible.

---

## What to build

Build a prototype with these logical components:

1. Trends Parser
2. Planning Agent
3. Platform-specific content planning agents
4. Workflow Agent
5. ComfyUI workflow integration layer
6. Telegram approval bot / approval handler
7. Publishing adapters
8. Minimal persistence and job tracking
9. A simple way to inspect runs, job states, and outputs

You may implement this as:
- one repo or multiple repos
- one backend or multiple services
- queue-based or workflow-engine-based
- API-first or agent-first

Choose the structure that gives the best prototype velocity.

---

## Functional expectations

The prototype should support this scenario:

1. collect trend signals
2. summarize them
3. generate platform-specific content plans
4. convert plans into executable generation tasks
5. run ComfyUI workflows
6. send output to Telegram
7. allow approval/rejection
8. loop rejected content back for another attempt
9. send approved content to publishing targets

The entire system should be traceable.

At minimum, each content item should have:
- source trend summary
- planning output
- workflow execution status
- generated assets
- approval state
- publish state

---

## Autonomy guidelines

You are allowed to make reasonable implementation decisions without asking for approval every time.

Use your judgment on:
- folder structure
- service boundaries
- database schema
- queue design
- prompt design
- agent architecture
- tool invocation structure
- integration style

Only stop for clarification if a missing decision would block meaningful progress.

Otherwise:
- choose the most practical default
- document the assumption
- proceed

---

## Technical freedom

You may choose any pragmatic stack.

Examples include:
- Python / FastAPI
- Node / TypeScript
- Postgres
- Redis
- Celery / RQ / Temporal / BullMQ
- Telegram Bot API
- ComfyUI API / workflow execution bridge

But do not feel locked to these.
Pick what makes the prototype work fastest and cleanest.

---

## Implementation priorities

Prioritize in this order:

### Priority 1
End-to-end working flow across:
trend input -> planning -> workflow -> Telegram approval -> publish/mock publish

### Priority 2
Clear modular architecture so components can later be upgraded independently

### Priority 3
Reasonable observability:
- logs
- status tracking
- run history
- failures

### Priority 4
Replaceable adapters for:
- social platforms
- ComfyUI workflows
- approval channels

---

## Non-goals for now

Do not overbuild.

This prototype does not need:
- enterprise auth
- full admin dashboards
- billing
- advanced permissions
- full production security hardening
- massive scaling support
- perfect social API coverage
- perfect trend intelligence

Focus on a coherent working prototype.

---

## Expected output from you

Produce:

### 1. Architecture proposal
A concise description of:
- services/modules
- data flow
- agent responsibilities
- queue/orchestration model
- how Telegram approval works
- how publishing is handled

### 2. Implementation plan
A step-by-step build plan with milestones.

### 3. Data model
Minimal schema/entities needed for runs, plans, assets, approvals, and publishing.

### 4. Prompt/agent design
How each agent thinks, what input/output schema it uses, and how handoffs work.

### 5. Code / project scaffold
Create the actual prototype implementation.

### 6. Run instructions
Explain how to start and test the system locally.

### 7. Honest assumptions and limitations
Document what is mocked, what is real, and what should be replaced later.

---

## Quality bar

Be practical, not academic.

Do not just describe the system.
Actually shape it into a buildable prototype.

Prefer:
- clean interfaces
- simple orchestration
- explicit state transitions
- modular connectors
- minimal but real working flow

Whenever you face ambiguity, optimize for:
- prototype speed
- clarity
- extensibility
- realistic behavior

---

## Core concept to preserve

This is a human-in-the-loop AI content factory:

- social trends come in
- agents decide what to create
- workflows generate content
- human approves in Telegram
- approved content gets routed to platforms

That behavior matters more than matching any exact internal implementation.

Build the prototype accordingly.