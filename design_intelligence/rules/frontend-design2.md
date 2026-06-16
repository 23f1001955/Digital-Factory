# Frontend-Design2 Scroll-Driven Rules

## Typography as Design
- Hero headings: 6rem minimum, tight line-height (0.9-1.0), heavy weight (700-800).
- Section headings: 3rem minimum, confident weight (600-700).
- Horizontal marquee text: 10-15vw, uppercase, letterspaced.
- Section labels: small (0.7rem), uppercase, letterspaced (0.15em+), muted color.

## No Cards, No Boxes
- NEVER use glassmorphism cards, frosted glass, or visible containers around text.
- Text sits directly on the background — clean, confident, editorial.
- Readability comes from: font weight (600+), text-shadow if needed.

## Color Zones
- Background color must shift between sections (light -> dark -> accent -> light).
- Define color zones: --bg-light, --bg-dark, --bg-accent.
- Text color inverts automatically: --text-on-light, --text-on-dark.

## Layout Variety
- Every page needs at least 3 different layout patterns:
  1. Centered — hero sections, CTAs
  2. Left-aligned — feature descriptions with product on right
  3. Right-aligned — alternate features
  4. Full-width — horizontal marquee text, stats rows
  5. Split — text on one side, supporting visual on the other
- Never use the same layout for consecutive sections.

## Animation Choreography
- Every section must use a DIFFERENT entrance animation.
- Elements within a section enter with staggered delays (0.08-0.12s between items).
- Sequence: label first -> heading -> body text -> CTA/button.
- At least one section must pin (stay fixed) while its contents animate internally.

## Stats & Numbers
- Display stats at 4rem+ font size.
- Numbers MUST count up via animation (never appear statically).
