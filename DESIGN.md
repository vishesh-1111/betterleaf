---
name: BetterLeaf
description: A spruce-ink, chalk-paper LaTeX resume workspace where the sun highlight marks only what the AI changed.
colors:
  spruce: "#10281f"
  spruce-deep: "#16362b"
  leaf: "#2e7d5b"
  leaf-bright: "#7fd1a6"
  sun: "#f2c14e"
  chalk: "#f2f4f0"
  paper: "#ffffff"
  muted: "#4e6158"
  muted-on-dark: "#7fa896"
  line: "#d3dad2"
  line-dark: "#35574a"
  code-text: "#d9e6de"
  dark-surface: "#0c1b15"
  dark-panel: "#12271f"
typography:
  display:
    fontFamily: "Bricolage Grotesque, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2.6rem, 5.6vw, 4.6rem)"
    fontWeight: 800
    lineHeight: 1.04
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Bricolage Grotesque, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2rem, 4vw, 3.1rem)"
    fontWeight: 800
    lineHeight: 1.04
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Bricolage Grotesque, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Instrument Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Instrument Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 600
    lineHeight: 1
  code:
    fontFamily: "ui-monospace, SF Mono, JetBrains Mono, Menlo, Consolas, monospace"
    fontSize: "0.8rem"
    lineHeight: 1.65
rounded:
  sm: "4px"
  card: "18px"
  panel: "26px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "28px"
  xl: "56px"
  section: "104px"
components:
  button-primary:
    backgroundColor: "{colors.spruce}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.pill}"
    padding: "17px 28px"
  button-primary-hover:
    backgroundColor: "{colors.leaf}"
    textColor: "{colors.chalk}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.spruce}"
    rounded: "{rounded.pill}"
    padding: "17px 28px"
  button-sm:
    backgroundColor: "{colors.spruce}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.pill}"
    padding: "11px 18px"
  pill-status:
    backgroundColor: "{colors.sun}"
    textColor: "{colors.spruce}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  pill-status-ok:
    backgroundColor: "{colors.leaf}"
    textColor: "{colors.paper}"
  plan-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.spruce}"
    rounded: "{rounded.card}"
    padding: "34px"
  final-box:
    backgroundColor: "{colors.leaf}"
    textColor: "{colors.paper}"
    rounded: "{rounded.panel}"
    padding: "76px 56px"
---

# Design System: BetterLeaf

## Overview

**Creative North Star: "The Honest Proof Sheet"**

BetterLeaf looks like a proof sheet on a printer's desk: deep spruce ink, chalk-white stock, hard-edged paper that casts a hard offset shadow, and one warm marker (sun) used only where the AI touched the text. The visual rule mirrors the product rule: the AI selects and orders, it does not invent, so every change must be visibly marked and nothing decorative competes with the resume itself.

The system is dense but calm. Marketing surfaces use large, tightly tracked display type on generous chalk; the workspace is a three-pane editor (files, LaTeX on spruce, PDF on a paper sheet) with 1.5px ink borders and no soft blur. Warmth comes from the leaf green and the sun marker, never from gradients or glass.

**Key Characteristics:**
- Spruce ink for text, chrome and the code window; chalk for pages; white only for paper.
- 1.5px ink borders and hard offset shadows instead of blurs.
- Pill buttons; 18px cards; the PDF sheet is the only element that reads as "paper".
- Sun yellow means "changed by the AI", nothing else.
- Display type is heavy and tight (800, -0.025em); body is quiet humanist sans.

## Colors

A restrained green-black palette on a faintly green off-white, with one warm highlight.

### Primary
- **Spruce Ink** (#10281f): text, top bar, code window, primary buttons, 1.5px borders, offset shadows. Never flips in dark mode.
- **Leaf Green** (#2e7d5b): the single accent: button hover, focus outline, active file row in dark mode, "1 page" success pill, final CTA block, PDF sheet shadow.

### Secondary
- **Sun Marker** (#f2c14e): highlight reserved for content the AI changed, the warning pill, and the editor caret.
- **Mint on Spruce** (#7fd1a6): LaTeX command tokens and accents on dark surfaces.

### Neutral
- **Chalk** (#f2f4f0): page and chrome background.
- **Paper** (#ffffff): the resume sheet, cards, dialog surface.
- **Moss Grey** (#4e6158): secondary text on chalk. **Sage on Spruce** (#7fa896) is its counterpart on dark.
- **Hairline Sage** (#d3dad2): dividers on chalk; **Dark Hairline** (#35574a) on spruce.
- **Deep Spruce Page** (#0c1b15) and **Dark Sheet** (#12271f): workspace surfaces in dark mode.

### Named Rules
**The Sun Means Changed Rule.** Sun yellow appears only on content the AI modified (plus the caret and the "2 pages" warning pill). Using it as decoration destroys its meaning.

**The One Accent Rule.** Leaf green is the only chromatic accent; no blue, purple, or gradients.

## Typography

**Display Font:** Bricolage Grotesque (with Helvetica Neue, Arial)
**Body Font:** Instrument Sans (with Helvetica Neue, Arial)
**Code Font:** system monospace stack (SF Mono / JetBrains Mono / Menlo)
**Resume Paper Font:** Latin Modern Roman / CMU Serif, used only inside the rendered resume sheet.

**Character:** A chunky, slightly eccentric grotesque for headings against a calm humanist sans; the serif appears only where the resume itself is shown.

### Hierarchy
- **Display** (800, clamp(2.6rem, 5.6vw, 4.6rem), 1.04): landing hero.
- **Headline** (800, clamp(2rem, 4vw, 3.1rem), 1.04): section headings.
- **Title** (700, 1.3rem, 1.2): cards and pair headings.
- **Body** (400, 17px marketing / 15px workspace, 1.6 / 1.5): paragraphs capped at 62ch.
- **Label** (600, 0.9-1rem): buttons, pills, tabs.
- **Code** (0.8rem marketing / 14px editor, 1.6-1.65): LaTeX source.

### Named Rules
**The Tight Heavy Display Rule.** Display type is always 700-800 with negative tracking; never light, never loosely tracked.

## Layout

Marketing pages use a 1180px centered wrap with 28px side padding and 104px section rhythm; two-column grids (about 1.35fr / 1fr) collapse at 960px and tighten again at 520px. The workspace is a full-height flex column: a 56px spruce top bar, then a horizontal resizable panel group (sidebar 15%, editor 42.5%, preview 42.5%) separated by 6px handles that turn leaf green on hover. Toolbars are 36px tall. Spacing is generous on marketing, compact (4-12px) inside tools.

## Elevation & Depth

Surfaces are flat at rest. Depth comes from 1.5px ink borders plus hard offset "print" shadows with zero blur, applied only to paper-like focal surfaces. Sticky nav uses a translucent chalk with a 10px backdrop blur as the single exception.

### Shadow Vocabulary
- **Studio block** (`box-shadow: 10px 10px 0 #10281f`): the hero editor mockup and the upload dialog.
- **Sheet block** (`box-shadow: 8px 8px 0 #2e7d5b`): the PDF preview sheet in the workspace.
- **Hairline paper** (`box-shadow: 0 1px 0 #d3dad2`): the mock resume page.

### Named Rules
**The No Blur Rule.** Shadows are hard offset blocks, never soft or diffused, and appear only on paper-like surfaces.

## Shapes

Pills (999px) for buttons, status chips and fake buttons; 18px for cards, the studio mockup and the upload dialog; 26px for the final CTA block; 8px for file rows; 3-4px for focus outlines and highlight marks. Borders are 1.5px spruce (1px sage hairline for list dividers). A dashed 1.5px border (#8fa398) marks "coming soon" cards.

## Components

### Buttons
- **Shape:** full pill (999px), 2px spruce border on marketing, 1.5px in the workspace.
- **Primary:** spruce fill, chalk text, 17px 28px padding (11px 18px small, 9px 16px workspace pill).
- **Hover / Focus:** fills leaf green with matching border; 3px leaf focus outline offset 3px (2px in the workspace).
- **Ghost:** transparent with spruce text; hover fills spruce.
- **Final-CTA variant:** spruce on leaf; hover flips to white with spruce text.

### Status pills
- Sun fill with spruce text for "2 pages" (needs attention); leaf fill with white text for "1 page" (done). Transitions 0.3s.

### Cards / Containers
- **Corner Style:** 18px. **Background:** paper with 1.5px spruce border. **Padding:** 34px.
- Coming-soon variant: transparent with dashed border.

### Code window
- Spruce fill, #d9e6de text, mint command tokens, muted sage braces, sun caret; changed lines carry a 3px left edge and sun tint.

### Navigation
- Marketing: sticky 68px chalk bar with hairline bottom border, Moss Grey links turning spruce. Workspace: 56px solid spruce bar with chalk wordmark.
- The wordmark is "Betterlea" plus a drawn leaf glyph forming the final "f"; keep it as the leaf SVG, not a font.

### File rows (sidebar)
- 8px radius; hover chalk; active spruce fill with chalk text (leaf fill with white in dark mode).

### Inputs and utility primitives
- Shadcn `Input`, `Select`, `Dialog`, `Tooltip` exist with the neutral grey tokens from `globals.css` and have not yet been brought onto the spruce identity (see Do's and Don'ts).

## Do's and Don'ts

### Do:
- **Do** use spruce (#10281f) for text, borders and primary fills; chalk (#f2f4f0) for pages.
- **Do** reserve sun (#f2c14e) for AI-changed content and the caret.
- **Do** use hard offset shadows (8-10px, zero blur) on paper-like focal surfaces only.
- **Do** keep buttons pill-shaped with a leaf-green hover.
- **Do** honor `prefers-reduced-motion`; motion is a single 0.5-0.7s settle (cubic-bezier(0.2, 0.7, 0.2, 1)) on load.
- **Do** treat the namespaced `.bl` / `.bl-ws` spruce tokens as the source of truth for new UI; migrate the shadcn neutral defaults toward them.

### Don't:
- **Don't** introduce blur shadows, glassmorphism, or gradients.
- **Don't** add a second chromatic accent beside leaf green.
- **Don't** use sun yellow decoratively.
- **Don't** ship new UI with the default shadcn neutral greys and 0.625rem radius; it contradicts the spruce identity.
- **Don't** use modals for core tailoring flow; PRODUCT.md requires inline, single-page interaction.
