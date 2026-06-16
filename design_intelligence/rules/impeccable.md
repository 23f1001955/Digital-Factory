# Impeccable Design Rules

## Color
- Verify contrast: body text must hit >= 4.5:1 against its background; large text (>=18px or bold >=14px) needs >= 3:1.
- Gray text on colored background looks washed out. Use a darker shade of the background's own hue.
- Use OKLCH color space. Pick a color strategy: Restrained (tinted neutrals + one accent), Committed (one saturated color carries 30-60%), Full palette (3-4 named roles), Drenched (surface IS the color).
- Cream/sand/beige body bg is the saturated AI default of 2026. Avoid warm-tinted near-white backgrounds.

## Typography
- Cap body line length at 65-75ch.
- Cap font-family count at 3 (display + body + optional mono).
- Hero/display heading ceiling: clamp() max <= 6rem (~96px).
- Display heading letter-spacing floor: >= -0.04em.
- Use text-wrap: balance on h1-h3; text-wrap: pretty on long prose.

## Layout
- Cards are the lazy answer. Use them only when truly the best affordance. Nested cards are always wrong.
- Flexbox for 1D, Grid for 2D.
- For responsive grids: repeat(auto-fit, minmax(280px, 1fr)).
- Build a semantic z-index scale. Never arbitrary values like 999.

## Motion
- Motion must be intentional, not an afterthought.
- Don't animate CSS layout properties unless truly needed.
- Ease out with exponential curves (ease-out-quart/quint/expo). No bounce, no elastic.
- Reduced motion is not optional: every animation needs a @media (prefers-reduced-motion: reduce) alternative.

## Absolute Bans
- NO gradient text (background-clip: text + gradient). Use a single solid color.
- NO glassmorphism as default. Rare and purposeful only.
- NO hero-metric template (big number, small label, stats, gradient accent).
- NO identical card grids (same-sized cards with icon + heading + text, repeated).
- NO tiny uppercase tracked eyebrow above every section.
- NO numbered section markers (01 / 02 / 03) as default scaffolding.

## Copy
- Every word earns its place. No restated headings, no intros that repeat the title.
- No em dashes. Use commas, colons, semicolons, or periods.
- No marketing buzzwords: streamline, empower, supercharge, leverage, transform, seamless.
- Button labels: verb + object. "Save changes" beats "OK".
