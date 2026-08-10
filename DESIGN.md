# Design

VaultLog product UI — light, restrained, Stripe-like clarity with a warm crimson accent.

## Color strategy

**Restrained.** Pure white surfaces; emotion lives in the crimson primary and cool slate neutrals.

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `oklch(1 0 0)` | Page background |
| `--surface` | `oklch(1 0 0)` | Cards, panels |
| `--surface-2` | `oklch(0.98 0.006 250)` | Subtle inset areas, table headers |
| `--ink` | `oklch(0.22 0.02 250)` | Primary text |
| `--muted` | `oklch(0.48 0.02 250)` | Secondary text, placeholders |
| `--border` | `oklch(0.90 0.01 250)` | Dividers, input borders |
| `--primary` | `oklch(0.48 0.16 20)` | Primary actions, active nav |
| `--primary-hover` | `oklch(0.42 0.16 20)` | Primary hover |
| `--primary-subtle` | `oklch(0.97 0.02 20)` | Active nav background |
| `--danger` | `oklch(0.52 0.18 25)` | Destructive actions |
| `--success` | `oklch(0.52 0.12 155)` | Success states |
| `--warning` | `oklch(0.65 0.12 75)` | Warnings, stale indicator |

No automatic dark mode in MVP.

## Typography

- **Family:** Geist Sans (UI), Geist Mono (secrets, codes, IDs)
- **Scale:** fixed rem — `text-sm` labels, `text-base` body, `text-lg` section titles, `text-xl` page titles
- **Measure:** prose blocks cap at ~65ch; tables and data may run wider

## Spacing & radius

- Panel radius: `12px` (`--radius-lg`)
- Control radius: `8px` (`--radius`)
- Page padding: `1rem` mobile, `1.5rem` desktop
- Section gap: `1.5rem` between major blocks

## Layout

- **Shell:** top bar with VaultLog wordmark, org name, capability-driven nav
- **Content:** `max-w-5xl` centered column with consistent `PageHeader`
- **Auth:** centered single-column form on `--surface-2` page bg

## Components

- Buttons: primary (crimson), secondary (border), ghost, danger — all with focus-visible ring
- Inputs: labeled, border + focus ring, inline error text
- Cards: border only, no wide drop shadows
- Dialog: native `<dialog>` for step-up and confirmations
- Empty states: icon + headline + one supporting line + optional CTA
- Skeletons: pulse blocks for list loading

## Motion

- Transitions: `180ms` ease-out on color, opacity, transform
- Reduced motion: disable pulse animations; instant state changes

## Z-index

| Layer | Value |
|-------|-------|
| dropdown | 40 |
| sticky header | 50 |
| modal backdrop | 60 |
| modal | 70 |
| toast | 80 |
