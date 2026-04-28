# Learncast — Post-Project Review

---

## Project Snapshot

Learncast addresses a common learning bottleneck: students miss class, re-reading dense notes is slow and passive, and traditional study formats don't fit modern schedules.

The tool targets anyone who learns on the go — commuters, gym-goers, busy professionals — and benefits auditory learners who retain information better through listening than reading.

Built as an MVP at the Ironhack AI Bootcamp, Learncast takes any PDF, .txt file, or pasted transcript and runs it through a three-stage Python pipeline: data cleaning, GPT-4o mini summarisation using the Feynman method and story arc structure, and OpenAI TTS audio generation. The output is a personalised MP3 podcast recap — selectable voice, adjustable tone — delivered in minutes instead of hours of re-reading.

At MVP level, the core loop works end-to-end. Known limitations include processing time for dense documents (~10 min), voice naturalness degrading at longer lengths, and URL scraping that needs further iteration.

---

## Stakeholder Impact

| # | Role | Need | Risk if Ignored | Influence | Interest |
|---|------|------|-----------------|-----------|----------|
| 1 | **End Users / Students & active learners** | Accurate, engaging audio recaps that fit into a busy schedule and help retain information without requiring dedicated study time. | Tool gets built for ideal conditions and never adopted — real usage patterns were never considered. | Low | High |
| 2 | **Founding Team** | Viable product-market fit, scalable architecture, and a clear path to monetisation. | Scope creep, technical debt, or a demo that never becomes production-ready — capital spent with no deployable outcome. | High | High |
| 3 | **IT / DevOps** | A stable, documented, deployable application with clear dependency management, no hardcoded secrets, and a reproducible environment. | App runs on one developer's laptop and nowhere else. | High | Low |
| 4 | **Legal / Compliance** | Clarity on what data is sent to third-party APIs, how user uploads are stored, and whether terms of service cover commercial use of generated content. | User transcripts containing confidential content are sent to external APIs without proper disclosure. | High | Low |
| 5 | **Finance** | Predictable, modelable cost per user interaction that allows building a viable pricing structure. | No rate limiting means a single large PDF triggers disproportionate API costs — unit economics become unviable. | High | Low |
| 6 | **Customer Support** | Clear error messages, internal documentation, and enough pipeline understanding to diagnose common failures without escalating to the dev team. | Users get cryptic error messages, support cannot handle tickets efficiently, churn increases. | Low | Medium |
| 7 | **B2B Customers (L&D programs)** | Guarantees on data privacy, data leak prevention, and quality commitments. | Enterprise deals fall through at the security review stage — locking Learncast out of the highest-revenue market segment. | High | High |

---

## From Demo to Real Project

### Operations: Monitoring and Incident Response

Currently the app has basic Python logging to the terminal and no alerting. If the OpenAI API goes down or a TTS call fails, the user sees an error message in the UI and nothing is logged persistently. For a production rollout we would add structured logging to a service like Datadog or Sentry, set up uptime monitoring, define uptime and reliability SLAs, and set up a simple on-call rotation so someone is notified when the app goes down during peak study hours.

### Security and Secrets Handling

During development we used a `.env` file locally and Hugging Face repository secrets for deployment — both reasonable for a prototype. For production we would move to a secrets manager such as AWS Secrets Manager or HashiCorp Vault, implement automatic secret rotation, and add a pre-commit hook that scans for accidentally committed credentials before every push.

### Data Lifecycle: PII, Retention and Training Data

Currently Learncast processes transcript content entirely in memory and passes it directly to the OpenAI API. No data is stored server-side and there is no policy around what happens to the content once it is sent to OpenAI for processing. In a production rollout we would need a clear data retention policy defining how long transcripts and audio files are kept and whether any content is used for model training. If the tool is used in an educational institution, transcripts may contain student Personally Identifiable Information (PII) — names, student IDs, or other identifying details — which would require GDPR or FERPA compliance, explicit consent flows, and the ability to delete data on request.

### Error Handling and Edge Cases

The current pipeline handles the happy path well: a clean transcript goes in and audio comes out. However, edge cases such as scanned PDFs, corrupted files, non-English transcripts, or very short inputs receive basic error messages with no recovery path or user guidance. A production version would need graceful degradation for each failure mode: OCR fallback for scanned documents, clear user-facing error messages, input validation before API calls are made, and retry logic for transient API failures. If Stage 2 fails, the raw cleaned transcript should be displayed. If Stage 3 fails, the generated script should remain readable so the student can still review content manually.

### API Budget and Cost Management

Learncast currently makes sequential OpenAI API calls per generation with token limits up to 8,192 per call. There is no rate limiting, cost tracking, or user quota system — a single user could trigger many expensive calls without any controls. For a real deployment we would implement per-user usage quotas, cost monitoring via the OpenAI usage dashboard, and alerts for unexpected spend. We would also evaluate whether gpt-4o-mini remains the best cost-quality tradeoff at scale, and potentially cache results for repeated or similar inputs to reduce redundant API calls.

### Handoff and Client Documentation

The project has a README covering setup and how to run the app locally, but it assumes the person deploying it is comfortable with conda environments, API keys, and command line tools. There is no user-facing documentation or onboarding material for non-technical users such as students or instructors. A production handoff would include a deployment guide with screenshots, a troubleshooting FAQ, a one-click install script, and training sessions for client staff. We would also define a support process covering who to contact when something breaks, what the response time commitment is, and how bugs are tracked and resolved. The definition of done would need to be agreed upfront with the client.

### Scope Beyond the Demo: Multilingual Support and Accessibility

The interface is currently functional but not optimised for end-user experience and is implicitly English-only. A proper UX design process would be needed for production, including user testing, accessible design patterns, clear error states, and progress indicators for longer processing times. For a global learner base or non-English bootcamp cohorts, language detection and multilingual TTS support would be required, along with audio accessibility features such as transcripts of the generated audio for users with hearing impairments.

---

## Revision Brief

### Before

At the start of the project, success meant getting the pipeline to work — upload a transcript, get audio out. There was no formal scope document, no defined user, and no risk assessment. We assumed the happy path: clean PDFs, English content, one user at a time, and an unlimited API budget. If it ran locally and produced a podcast, we considered it done.

### After

Having thought through stakeholders and production reality, we would reframe success around three things: who the tool is actually for, what it needs to handle reliably, and what done really means. We would narrow the MVP to a specific user — for example, Ironhack students reviewing bootcamp material in English — rather than building for everyone at once. We would also open the scope to include instructors as a second user type, since teachers uploading their own class PDFs is a natural extension with different needs around content control and accuracy. One of the clearest gaps was the absence of non-functional requirements: we discovered mid-build that more API calls produced better output but pushed wait times up to 10 minutes — a tradeoff a real client would need to approve upfront, with an agreed acceptable response time defined before development started. Finally, we would add a security review gate before any external deployment, a cost ceiling per user session, and a clearer definition of done that includes edge case handling and performance benchmarks, not just the happy path.
