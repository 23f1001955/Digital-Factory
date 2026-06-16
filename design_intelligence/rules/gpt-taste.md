# GPT-Taste Design Rules

## AIDA Structure
- Attention (Hero): Cinematic, clean, wide layout.
- Interest (Features/Bento): High-density, mathematically perfect grid.
- Desire (GSAP Scroll/Media): Pinned sections, horizontal scroll, text-reveals.
- Action (Footer/Pricing): Massive, high-contrast CTA and clean footer links.
- Add huge vertical padding between sections (py-32 md:py-48). Sections must feel like distinct chapters.

## Hero Architecture
- Hero must NEVER exceed 2-3 lines. Use ultra-wide containers (max-w-5xl, max-w-6xl, w-full).
- Font size: clamp(3rem, 5vw, 5.5rem).
- Three hero layouts: Cinematic Center (centered text, wide, full-bleed bg), Artistic Asymmetry (text left, floating image right), Editorial Split (text left, image right, massive negative space).
- Buttons must be perfectly legible. Dark bg = white text. Light bg = dark text.
- BANNED: floating stamp/badge icons on text, pill-tags under hero, raw data/stats in hero.

## Gapless Bento Grid
- Use grid-auto-flow: dense on every bento grid.
- Mathematically verify col-span and row-span values interlock perfectly.
- 3-5 highly intentional cards are better than 8 messy ones.
- Fill cards with large imagery, dense typography, or CSS effects.

## Motion
- Every clickable card and image must react with hover effects.
- Scroll pinning: pin a section title on left while gallery scrolls on right.
- Images: start small (scale: 0.8), grow to 1.0 on scroll, fade out on exit.

## BANNED
- NO meta-labels: "SECTION 01", "QUESTION 05", "ABOUT US".
- NO cheap labels. They look unprofessional.
