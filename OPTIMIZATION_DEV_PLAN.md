# Optimization Development Plan

## Goals
- Speed: deliver a usable "fast scan" result quickly, then deepen only if needed.
- Accuracy: reduce OCR artifacts and avoid hallucinated outputs.
- UX clarity: show what was analyzed, what is missing, and what needs review.
- Cost control: minimize OCR/LLM calls with caching and routing.

## Scope
- Contract Review Agent (primary focus in this plan)
- Peer PER Analysis (phase 3 extension)
- Investment Report Drafting (phase 3 extension)

## Non-goals
- Model fine-tuning or custom model training
- Legal advice or legal judgment automation

## Architecture (High-Level)
1) Fast-first pipeline: quick scan → risk summary → drill-down
2) OCR two-layer: local OCR → Claude cleanup (text-only)
3) Rule-based extraction + weighted segment ranking
4) Multi-turn drill-down with evidence snippets
5) Cache by file hash + settings

## Milestones and Status
### Phase 0 — Baseline UX and Safety (Done)
- [x] Results-first layout (summary before details)
- [x] Masking default ON and file-name hiding
- [x] Clear progress UI and OCR status

### Phase 1 — Fast OCR and Evidence Quality (Done)
- [x] Fast scan with OCR page budget and selection strategy
- [x] Local OCR + Claude cleanup (text-only refinement)
- [x] OCR engine reporting and fallback handling
- [x] Weighted segment ranking and clause weight display

### Phase 2 — Caching and Reuse (In Progress)
- [x] Per-document cache keyed by file hash + OCR settings
- [ ] Cache invalidation strategy for major extraction changes
- [ ] Optional UI: "clear cache" per document

### Phase 3 — Cross-Module Optimization (Planned)
- [ ] Peer analysis: cache heavy tool outputs by file hash
- [ ] Peer analysis: outlier/consistency checks for metrics
- [ ] Report drafting: template slots + validation checks
- [ ] Report drafting: quick summary view before full draft

## Acceptance Criteria
- Fast scan returns a usable risk summary within the first run.
- OCR artifacts reduced (spacing/garbling) compared to raw OCR text.
- Repeat analyses of the same file reuse cache.
- User can understand which document(s) are missing for comparison.

## Operational Notes
- Local OCR requires `tesseract-ocr` and `tesseract-ocr-kor`.
- Claude cleanup uses text-only calls (no image uploads).
- Cache storage is local (`temp/cache/...`) and non-persistent on some hosts.

## Risks and Mitigations
- OCR accuracy variance → mitigate with OCR budget tuning + refine toggle.
- Cache staleness → mitigate with versioned cache keys.
- Document variety → mitigate with weighted segments + drill-down Q&A.

## Next Implementation Targets
1) Cache invalidation / reset UX
2) Peer/Report caching and validation
