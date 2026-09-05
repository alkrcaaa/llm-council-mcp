# Design DNA — llm-council

Direction: The Deliberation Chamber — authoritative dark obsidian & warm brass, architectural geometry, crisp judicial hierarchy
Why: A high-stakes council where frontier models debate, cross-examine, and hand down consensus verdicts on critical decisions.

## Typography
- Display: 'Syne', sans-serif (weights: 700, 800) — geometric, sculpted, authoritative
- Body: 'Plus Jakarta Sans', sans-serif (weights: 400, 500, 600) — clean, modern, ultra-readable
- Mono: 'JetBrains Mono', monospace (weights: 400, 500) — token metrics, latency, confidence, pricing

Scale:
- Hero / Title: 28px–32px, weight 800, tracking -0.03em
- Section Headings: 18px–20px, weight 700, tracking -0.02em
- Body: 14px, weight 400, line-height 1.6
- Micro / Badges: 11px–12px, weight 600, uppercase, tracking +0.06em
- Weight contrast: 400 vs 800 (ratio 400)

## Palette (CSS Variables — Single Source of Truth)
- Canvas Background: `--bg-canvas: #090b0e;` (deep monolithic obsidian)
- Elevated Surface: `--bg-surface: #11141a;` (matte carbon card)
- Surface Hover / Active: `--bg-surface-hover: #181d26;`
- Border Hairline: `--border-subtle: rgba(255, 255, 255, 0.07);`
- Border Active / Contrast: `--border-active: rgba(229, 169, 60, 0.4);`
- Text Primary: `--text-primary: #f0f2f5;`
- Text Secondary: `--text-secondary: #8b949e;`
- Text Muted: `--text-muted: #545d68;`
- Dominant Accent (Brass / Amber): `--accent-brass: #e5a93c;` (warm verdict gold)
- Accent Hover: `--accent-brass-hover: #f3be5d;`
- Semantic Status:
  - Consensus / Ok: `--status-consensus: #10b981;` (emerald)
  - Debate / Disagreement: `--status-divergence: #f59e0b;` (amber)
  - Critical / Error: `--status-critical: #ef4444;` (crimson)
  - Info / Model: `--status-model: #6366f1;` (deep indigo)

Rule: The brass accent is used exclusively for primary actions, active stage markers, and the Chairman's final synthesis. Never blanketed.

## Layout Signature
- **Left Ledger Rail:** A slim, dense, vertical control column with crisp hairline borders, quick session switcher, and compact indicators.
- **Stage Progression Chambers:**
  - Stage 1: The Model Rostrum (distinct cards per model with confidence badges and reasoning drawers).
  - Stage 2: The Peer Examination Matrix (anonymized cross-rankings with weighted delta scores).
  - Stage 3: The Chairman Gavel (embossed synthesis chamber with distinctive brass border accent).
- **Hairline Framing:** 1px subtle borders (`rgba(255, 255, 255, 0.07)`), 6px/8px radii (geometric, not bubbly pill-shapes).

## Motion Signature
- Subtle 150ms ease-out transitions on hover/select states.
- 1 orchestrated stagger on stage appearance (`opacity: 0; transform: translateY(6px)` to `opacity: 1; transform: translateY(0)` over 220ms).
- No distracting bouncy animations.

## Signature Element
- **The Stage Seal:** Distinctive numeric step glyphs (`01`, `02`, `03`) in monospace brass tags, combined with model attribution badges.

## Banned in this Project
- Inter / Roboto / system-ui default fonts
- Purple/violet generic AI gradients
- Three equal-width bootstrap cards in a row
- Glassmorphism / blurry frosted glass backgrounds
- Emoji as primary UI icons
- Generic bright blue buttons (`#4a90e2`, `#3b82f6`)
