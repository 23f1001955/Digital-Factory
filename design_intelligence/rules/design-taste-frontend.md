# Design-Taste-Frontend Rules (Taste Skill)

## Brief Inference
- Read the room before designing. Infer page kind (SaaS landing, portfolio, redesign, editorial), vibe (minimalist, calm, brutalist, premium, playful, editorial), audience (B2B, consumer, recruiter), and quiet constraints (a11y, regulated industry).
- Output a one-line "Design Read" before generating.

## Three Dials
- DESIGN_VARIANCE (1-10): 1=Perfect Symmetry, 10=Artsy Chaos. Default 8.
- MOTION_INTENSITY (1-10): 1=Static, 10=Cinematic. Default 6.
- VISUAL_DENSITY (1-10): 1=Airy, 10=Cockpit. Default 4.

## Anti-Default Discipline
- NO AI-purple gradients, NO centered hero over dark mesh, NO three equal feature cards.
- NO generic glassmorphism on everything, NO infinite-loop micro-animations everywhere.
- NO Inter + slate-900 as default.

## Typography
- Display/Headlines: default text-4xl md:text-6xl tracking-tighter leading-none.
- Body: default text-base leading-relaxed max-w-[65ch].
- Sans choices: Geist, Outfit, Cabinet Grotesk, Satoshi. NOT Inter as default.
- Discouraged serif as default (banned: Fraunces, Instrument Serif).
- Max 1 accent color. Saturation < 80% by default.

## Color
- NO "AI Purple/Blue glow" aesthetic. Use neutral bases (Zinc/Slate/Stone) with high-contrast accents (Emerald, Electric Blue, Deep Rose, Burnt Orange).
- Once an accent color is chosen, use it on the WHOLE page.
- No pure black (#000) or pure white (#fff). Use off-black and off-white.

## Hero Rules
- Hero MUST fit in initial viewport. Headline max 2 lines on desktop, subtext max 20 words.
- Navigation max 80px desktop, single line.
- No duplicate CTA intent (same label per intent across whole page).
- CTA text MUST fit on one line at desktop.

## Layout Discipline
- Zigzag alternation cap: max 2 consecutive text+image split sections.
- Bento grids: exact cell count matching content (no empty cells).
- Max 1 eyebrow per 3 sections.
- Cards only when elevation communicates real hierarchy.
- Hero top padding max pt-24 (6rem) at desktop.

## Motion
- Animate ONLY transform and opacity. Never top, left, width, height.
- Every animation needs a @media (prefers-reduced-motion: reduce) alternative.
- GSAP ScrollTrigger: start at "top top", pin the wrapper, scrub the inner track.
- For simple scroll reveals, prefer Motion's whileInView over GSAP.

## Landing Page Specific
- Landing pages live on first impression. Cut ruthlessly.
- Short headline (<= 8 words) + sub-paragraph (<= 25 words) + one visual or CTA per section.
- Real images required. Text-only pages with fake-screenshot divs are slop.
- No div-based fake product previews. Use real screenshots or generated images.
