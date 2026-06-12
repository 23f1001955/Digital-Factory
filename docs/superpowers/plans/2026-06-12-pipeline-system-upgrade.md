# Pipeline System Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Digital Product Factory pipeline with structured prompts, premium PDF design system, format-differentiated content, proper Notion databases, and bug fixes.

**Architecture:** All changes stay within existing DOE (Directive → Orchestration → Execution) layers. No new product types. Core agents get enhanced prompts via template files, renderers get a 400-line CSS design system, Notion agent gets database creation capability, and format-awareness is added via a new `format` field on `ComponentSpec`.

**Tech Stack:** Python 3.11+, Jinja2 (prompt templates + HTML templates), pydantic v2, Notion API (databases), Playwright (PDF), CSS3 with `@page` rules.

---

### Task 1: Add `__init__.py` to all packages

**Files:**
- Create: `orchestrator/__init__.py`
- Create: `agents/__init__.py`
- Create: `cli/__init__.py`
- Create: `renderers/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create all `__init__.py` files**

```python
# Each file is just an empty file (marks directory as Python package)
# orchestrator/__init__.py
# agents/__init__.py
# cli/__init__.py
# renderers/__init__.py
# tests/__init__.py
```

Write each as an empty file.

- [ ] **Step 2: Commit**

```bash
git add orchestrator/__init__.py agents/__init__.py cli/__init__.py renderers/__init__.py tests/__init__.py
git commit -m "chore: add __init__.py to all packages"
```

---

### Task 2: Fix `{slug}.zip` literal filename in packaging_agent

**Files:**
- Modify: `agents/packaging_agent.py:12`

- [ ] **Step 1: Apply the fix**

In `packaging_agent.py`, replace:
```python
output_zip = os.path.join("outputs", job_spec.slug, component.output)
```
with:
```python
output_path = component.output.replace("{slug}", job_spec.slug)
output_zip = os.path.join("outputs", job_spec.slug, output_path)
```

- [ ] **Step 2: Commit**

```bash
git add agents/packaging_agent.py
git commit -m "fix: interpolate {slug} in packager output filename"
```

---

### Task 3: Add `format` field to ComponentSpec model

**Files:**
- Modify: `orchestrator/models.py`

- [ ] **Step 1: Add format field to ComponentSpec**

Replace:
```python
class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
```

With:
```python
from typing import List, Literal, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"
```

Leave the rest of the file unchanged.

- [ ] **Step 2: Also add display_name to JobSpec**

Replace:
```python
class JobSpec(BaseModel):
    slug: str
    product_type: str
    niche: str
    theme: str = "default"
    notion_sync: bool = False
    notion_parent_page_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

With:
```python
class JobSpec(BaseModel):
    slug: str
    product_type: str
    niche: str
    theme: str = "default"
    display_name: Optional[str] = None
    notion_sync: bool = False
    notion_parent_page_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 3: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add format and display_name fields to models"
```

---

### Task 4: Create all prompt template files

**Files:**
- Create: `prompts/database.j2`
- Create: `prompts/sources.j2`
- Create: `prompts/report.j2`
- Create: `prompts/guide.j2`
- Create: `prompts/sops.j2`
- Create: `prompts/templates.j2`
- Create: `prompts/prompts.j2`
- Create: `prompts/image_prompts.j2`
- Create: `prompts/automation_blueprint.j2`
- Create: `prompts/notion_crm.j2`
- Create: `prompts/setup_guide.j2`

- [ ] **Step 1: Create `prompts/database.j2`**

```jinja2
You are an expert researcher and curator specializing in {{ niche }}.

Generate a JSON array of 7-10 key resources, tools, platforms, or communities in the "{{ niche }}" niche.

Each item MUST have these fields:
- "name": Short resource name (2-5 words)
- "description": 1-2 sentence explanation of what it does and why it matters
- "url": A real, believable URL (use example.com format if unsure)
- "pricing_model": One of "Free", "Freemium", "Subscription", "One-time", "Contact for pricing"

CRITICAL RULES:
- Return ONLY raw JSON array — no markdown, no code blocks, no text
- Array must start with `[` and end with `]`
- No trailing commas
- All strings in double quotes

Example format:
[
  {
    "name": "Example Tool",
    "description": "A platform that helps professionals in this niche automate their workflow.",
    "url": "https://example.com",
    "pricing_model": "Freemium"
  }
]
```

- [ ] **Step 2: Create `prompts/sources.j2`**

```jinja2
You are a trend analyst specializing in {{ niche }}.

Write a Markdown document listing the top 5 current trends, shifts, or emerging patterns in "{{ niche }}".

For each trend include:
- **Trend name** as an H3 heading
- **Description**: 2-3 sentences explaining the trend
- **Why it matters**: 1-2 sentences on impact
- **Key players/examples**: 1-2 real examples

Start with a brief H2 "Current Trends & Sources" introduction paragraph.

Tone: Professional, insightful, data-informed. Avoid generic buzzwords.
```

- [ ] **Step 3: Create `prompts/report.j2`**

```jinja2
You are a senior industry analyst producing a comprehensive research report on "{{ niche }}".

CONTEXT MATERIALS:

Database (tools & resources):
{{ database }}

Trends & Sources:
{{ sources }}

---

Write a comprehensive Markdown research report with this EXACT structure:

# {{ title }}

## Executive Summary
2-3 paragraph overview of the niche landscape, key findings, and recommendations.

## Market Overview
Analysis of the current state of {{ niche }}, including size, growth trajectory, and key segments.

## Key Trends & Developments
Detailed exploration of the major trends shaping this space. Reference the sources data above.

## Tools & Resources Landscape
Analysis of the tools/resources from the database. Group them by category. Explain which tools are best for which use case.

## Competitive Analysis
Key players, their positioning, strengths and weaknesses.

## Recommendations
Actionable recommendations for someone entering or operating in this niche.

## Conclusion
Final thoughts and outlook.

## Sources
List all sources referenced.

Tone: Analytical, authoritative, actionable. Minimum 1500 words.
```

- [ ] **Step 4: Create `prompts/guide.j2`**

```jinja2
You are an expert practitioner and teacher in {{ niche }}.

Write a comprehensive beginner's guide (Markdown) for "{{ niche }}".

Use this EXACT structure:

# {{ title }}

## Introduction: What is This & Why Does It Matter?
Explain the core concept and its importance. Hook the reader with a relatable problem this solves.

## Section 1: Getting Started
Step-by-step instructions for absolute beginners. What do they need to know first? What tools/prerequisites?

## Section 2: Core Concepts
Break down the 3-5 most important concepts, each as an H3 subsection with clear explanation and examples.

## Section 3: Practical Workflow
A walkthrough of the typical workflow — from start to finish. Numbered steps.

## Section 4: Common Pitfalls & How to Avoid Them
3-5 common mistakes beginners make, with specific advice to avoid each.

## Section 5: Tools & Resources
Recommend specific tools, templates, or resources. Explain WHY each is recommended.

## Conclusion & Next Steps
Summarize and tell the reader what to do next.

CONTEXT (use these to align with other components):
{{ context }}

Tone: Encouraging but authoritative. Use real examples. Avoid fluff. Minimum 1000 words.
```

- [ ] **Step 5: Create `prompts/sops.j2`**

```jinja2
You are a senior operations manager specializing in {{ niche }}.

Write 3 detailed Standard Operating Procedures (SOPs) in Markdown for "{{ niche }}".

Each SOP MUST follow this structure:

## SOP N: [Title]

**Purpose:** One sentence explaining what this SOP achieves.

**Scope:** Who this applies to and when.

**Procedure Steps:**
1. [Action verb] — [specific detail on how to execute]
2. [Action verb] — [specific detail]
3. ... (continue as needed)

**Expected Outcome:** What success looks like.

**Related SOPs:** [Cross-reference other SOPs]

---

Guidelines:
- Each SOP must have at least 8-12 detailed steps
- Steps must be actionable, not theoretical
- Include specific numbers, timeframes, and thresholds where relevant
- SOPs should cover end-to-end operational workflows for this niche

CONTEXT (align with these existing components):
{{ context }}

Tone: Direct, procedural, no explanations or theory. Just instructions.
```

- [ ] **Step 6: Create `prompts/templates.j2`**

```jinja2
You are a productivity system designer for {{ niche }}.

Create 3 ready-to-use templates (Markdown) for daily professional use in "{{ niche }}".

Each template must:
1. Have a clear H2 title with emoji
2. Include fill-in-the-blank fields in `[bracket notation]`
3. Be immediately usable — copy, paste, fill

Templates should cover:
1. A planning/strategy template
2. A tracking/monitoring template
3. A review/retrospective template

Each template should be 20-40 lines with clear sections, tables where useful, and checkboxes for tasks.

CONTEXT (align with existing components):
{{ context }}

Tone: Practical, minimalist, immediately useful.
```

- [ ] **Step 7: Create `prompts/prompts.j2`**

```jinja2
You are an advanced prompt engineer specializing in {{ niche }}.

Write 5 high-quality ChatGPT prompts (Markdown) that professionals in "{{ niche }}" would find extremely valuable.

For EACH prompt, provide:

## N. [Prompt Name]

**Use case:** Who should use this and when.

**Prompt:**
```
[The full prompt text, ready to copy and paste into ChatGPT. Include placeholders in [brackets].]
```

**Expected output:** What the user can expect to receive.

**Pro tip:** How to customize or iterate on the results.

Rules:
- Each prompt must be 5-15 sentences, not 1-2 lines
- Prompts must use advanced techniques (role-playing, chain-of-thought, formatting instructions, constraints)
- Cover different use cases (planning, analysis, creation, problem-solving, learning)
- Must be genuinely useful, not generic

CONTEXT (align with existing components):
{{ context }}

Tone: Practical, advanced, no beginner-level prompts.
```

- [ ] **Step 8: Create `prompts/image_prompts.j2`**

```jinja2
You are a creative director and visual strategist for {{ niche }}.

Generate exactly 4 visual prompts for a text-to-image AI (like DALL-E) that capture the essence of "{{ niche }}".

Each prompt must:
- Be 2-3 detailed sentences
- Specify style (e.g., "photorealistic", "flat illustration", "cinematic lighting")
- Include mood/atmosphere
- Reference color palette
- Be visually distinct from the others

Cover different aspects of the niche — don't repeat the same concept.

Return ONLY a raw JSON array of 4 strings — no markdown, no text outside the array.

Example:
["Prompt 1 describing first visual concept.", "Prompt 2 describing second visual concept.", "Prompt 3...", "Prompt 4..."]
```

- [ ] **Step 9: Create `prompts/automation_blueprint.j2`**

```jinja2
You are an automation architect specializing in {{ niche }}.

Write a detailed, step-by-step Automation Blueprint (Markdown) for setting up Zapier/Make automations in "{{ niche }}".

Structure:
# {{ title }}

## Overview
What this automation system does and who it's for.

## Trigger Sources
List each trigger (e.g., "New email in Gmail", "New row in Google Sheets").

## Automation 1: [Name]
- **Trigger**: [App + Event]
- **Action 1**: [App + Operation]
- **Action 2**: ...
- **Outcome**: What this saves

## Automation 2: ... (repeat for 3-5 automations)

## Setup Instructions
Step-by-step for each automation.

CONTEXT (align with existing components):
{{ context }}

Tone: Technical, specific, copy-and-paste ready.
```

- [ ] **Step 10: Create `prompts/notion_crm.j2`**

```jinja2
You are a Notion system architect specializing in {{ niche }}.

Design a Markdown document representing a CRM/tracker structure (tables/lists of contacts, pipelines, databases) tailored for "{{ niche }}".

Structure:
# {{ title }}

## Database 1: [Name]
- **Properties**: [List of column names with types]
- **Views**: [Table, Kanban, Calendar — which and why]
- **Relations**: [Links to other databases]

## Database 2: ... (repeat for 3-4 databases)

## Dashboard View
How the main page should be laid out.

CONTEXT (align with existing components):
{{ context }}

Tone: Instructional, database-designer mindset.
```

- [ ] **Step 11: Create `prompts/setup_guide.j2`**

```jinja2
You are a deployment engineer for {{ niche }}.

Write a comprehensive Setup Guide (Markdown) for deploying the systems described in this kit for "{{ niche }}".

Structure:
# {{ title }}

## Prerequisites
What's needed before starting.

## Step 1: [First setup task]
Detailed instructions.

## Step 2: [Next task]
...

## Configuration
Settings, environment variables, API keys needed.

## Troubleshooting
Common issues and solutions.

CONTEXT (align with existing components):
{{ context }}

Tone: Technical, step-by-step, beginner-friendly. Assume no prior knowledge.
```

- [ ] **Step 12: Commit**

```bash
git add prompts/
git commit -m "feat: add structured prompt templates for all agents"
```

---

### Task 5: Update content_agent to use prompt templates

**Files:**
- Modify: `agents/content_agent.py`
- Modify: `agents/research_agent.py`

- [ ] **Step 1: Rewrite content_agent.py**

Replace entire file content:

```python
import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"

prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))

CONTEXT_EXTRACT_PROMPT = """
Given the following document, extract 3-5 key themes, concepts, or takeaways that would help align another document on the same topic.

Document:
{doc_text}

Return only a bullet list of 3-5 key points, each 1 sentence.
"""

def _extract_context(doc_path: str) -> str:
    """Extract key themes from a dependency document for cross-component context."""
    try:
        with open(doc_path, "r") as f:
            text = f.read()
        # For large docs, take first 3000 chars
        excerpt = text[:3000]
        prompt = CONTEXT_EXTRACT_PROMPT.format(doc_text=excerpt)
        return generate_text(prompt)
    except Exception as e:
        logger.warning(f"Context extraction failed for {doc_path}: {e}")
        return ""


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        template_name = f"{component.id}.j2"
        template_path = os.path.join(PROMPT_DIR, template_name)

        if not os.path.exists(template_path):
            # Fallback to generic prompt
            prompt = f'You are an expert content creator for the niche: "{job_spec.niche}".\n'
            prompt += f"Write a comprehensive document (Markdown) covering {component.id}. Must start with an H1 title."
            content = generate_text(prompt)
        else:
            # Build template variables
            template = prompt_env.get_template(template_name)

            render_context = {
                "niche": job_spec.niche,
                "title": job_spec.display_name or job_spec.niche,
                "context": "",
            }

            # Inject dependency context
            for dep in component.depends_on:
                dep_path = context.get(dep)
                if dep_path and os.path.exists(dep_path):
                    extracted = _extract_context(dep_path)
                    render_context["context"] += f"\n### From {dep}:\n{extracted}\n"

            # Load database/sources data if available
            for data_key in ("database", "sources"):
                data_path = context.get(data_key)
                if data_path and os.path.exists(data_path):
                    with open(data_path, "r") as f:
                        render_context[data_key] = f.read()
                else:
                    render_context[data_key] = ""

            # Handle format-aware generation
            content_mode = getattr(component, "format", "full")

            if content_mode == "guide":
                render_context["mode"] = "guide"
            elif content_mode == "notion":
                render_context["mode"] = "notion"
            else:
                render_context["mode"] = "full"

            prompt = template.render(**render_context)
            content = generate_text(prompt)

        if not content.startswith("#"):
            logger.warning(f"Component {component.id} missing H1, retrying...")
            prompt += "\n\nCRITICAL: Start the response with an # H1 Title."
            content = generate_text(prompt)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Content agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Rewrite research_agent.py**

Replace entire file content:

```python
import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"
prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        template_name = f"{component.id}.j2"
        template = prompt_env.get_template(template_name)

        prompt = template.render(
            niche=job_spec.niche,
            title=job_spec.display_name or job_spec.niche,
        )

        content = generate_text(prompt)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Research agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 3: Update requirements.txt to ensure jinja2 is listed**

Check if jinja2 is already in requirements.txt:
```bash
Get-Content requirements.txt | Select-String "jinja2"
```
If not present, add `jinja2>=3.1.0` to requirements.txt.

- [ ] **Step 4: Commit**

```bash
git add agents/content_agent.py agents/research_agent.py
git commit -m "feat: use structured prompt templates in content and research agents"
```

---

### Task 6: Redesign base.css — Full premium design system

**Files:**
- Modify: `templates/shared/base.css`

- [ ] **Step 1: Write the new base.css**

Replace entire file content:

```css
:root {
  /* Typography */
  --font-heading: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  --font-size-h1: 36px;
  --font-size-h2: 24px;
  --font-size-h3: 18px;
  --font-size-h4: 16px;
  --font-size-body: 14px;
  --font-size-small: 12px;
  --font-size-caption: 10px;
  --line-height-body: 1.7;
  --line-height-heading: 1.2;
  --font-weight-bold: 700;
  --font-weight-semibold: 600;
  --font-weight-normal: 400;
  --font-weight-light: 300;
  --letter-spacing-tight: -0.02em;
  --letter-spacing-wide: 0.05em;

  /* Colors — default theme (clean professional) */
  --color-text-primary: #1d1d1f;
  --color-text-secondary: #6e6e73;
  --color-text-muted: #86868b;
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f5f5f7;
  --color-accent: #0066cc;
  --color-accent-hover: #004499;
  --color-border: #e5e5ea;
  --color-border-light: #f0f0f2;
  --color-success: #30d158;
  --color-warning: #ff9f0a;
  --color-error: #ff453a;
  --color-code-bg: #f4f4f5;
  --color-quote-border: #0066cc;

  /* Layout */
  --page-width: 210mm;
  --page-height: 297mm;
  --page-padding: 20mm 25mm;
  --cover-height: 200mm;
  --section-spacing: 32px;
  --element-spacing: 16px;

  /* PDF print */
  --header-font-size: 9px;
  --footer-font-size: 8px;
}

{% if theme == 'luxury-dark' %}
  @import url('themes/luxury-dark.css');
{% elif theme == 'editorial' %}
  @import url('themes/editorial.css');
{% elif theme == 'minimal' %}
  @import url('themes/minimal.css');
{% endif %}

/* ====== PDF Print Rules ====== */
@page {
  size: A4;
  margin: 20mm 25mm;
  @bottom-center {
    content: counter(page);
    font-family: var(--font-body);
    font-size: var(--footer-font-size);
    color: var(--color-text-muted);
  }
}

@page :first {
  @bottom-center {
    content: none;
  }
}

/* ====== Base ====== */
* {
  box-sizing: border-box;
}

body {
  font-family: var(--font-body);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
  color: var(--color-text-primary);
  background: var(--color-bg-primary);
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
}

.page {
  width: var(--page-width);
  min-height: var(--page-height);
  padding: var(--page-padding);
  margin: 0 auto;
}

/* ====== Cover Page ====== */
.cover {
  height: var(--cover-height);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  page-break-after: always;
}

.cover-accent {
  width: 60px;
  height: 4px;
  background: var(--color-accent);
  margin-bottom: 32px;
  border-radius: 2px;
}

.cover-title {
  font-family: var(--font-heading);
  font-size: 48px;
  font-weight: var(--font-weight-bold);
  letter-spacing: var(--letter-spacing-tight);
  line-height: var(--line-height-heading);
  margin-bottom: 16px;
  color: var(--color-text-primary);
}

.cover-subtitle {
  font-size: 20px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
  font-weight: var(--font-weight-normal);
}

.cover-meta {
  font-size: var(--font-size-small);
  color: var(--color-text-muted);
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.cover-meta span {
  display: inline-block;
  margin-right: 24px;
}

/* ====== Table of Contents ====== */
.toc {
  page-break-after: always;
  padding: 0;
}

.toc h2 {
  font-size: var(--font-size-h2);
  margin-bottom: 24px;
  border: none;
  padding: 0;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dotted var(--color-border-light);
  font-size: var(--font-size-body);
}

.toc-item a {
  color: var(--color-text-primary);
  text-decoration: none;
}

.toc-item-h2 {
  padding-left: 0;
  font-weight: var(--font-weight-semibold);
}

.toc-item-h3 {
  padding-left: 20px;
  font-size: var(--font-size-small);
  color: var(--color-text-secondary);
}

/* ====== Typography ====== */
h1 {
  font-family: var(--font-heading);
  font-size: var(--font-size-h1);
  font-weight: var(--font-weight-bold);
  letter-spacing: var(--letter-spacing-tight);
  margin-top: 0;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--color-accent);
  page-break-before: always;
}

h1:first-of-type {
  page-break-before: avoid;
}

h2 {
  font-family: var(--font-heading);
  font-size: var(--font-size-h2);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.01em;
  margin-top: var(--section-spacing);
  margin-bottom: var(--element-spacing);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

h3 {
  font-family: var(--font-heading);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
  margin-top: 24px;
  margin-bottom: 12px;
}

h4 {
  font-family: var(--font-heading);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  margin-top: 20px;
  margin-bottom: 10px;
}

p {
  margin-bottom: var(--element-spacing);
}

/* ====== Links ====== */
a {
  color: var(--color-accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* ====== Lists ====== */
ul, ol {
  margin-bottom: var(--element-spacing);
  padding-left: 24px;
}

li {
  margin-bottom: 6px;
}

li > ul, li > ol {
  margin-bottom: 0;
  margin-top: 4px;
}

/* ====== Blockquotes ====== */
blockquote {
  margin: var(--element-spacing) 0;
  padding: 12px 20px;
  border-left: 4px solid var(--color-quote-border);
  background: var(--color-bg-secondary);
  font-style: italic;
  color: var(--color-text-secondary);
}

blockquote p:last-child {
  margin-bottom: 0;
}

/* ====== Code Blocks ====== */
code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--color-code-bg);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--color-text-primary);
}

pre {
  background: var(--color-code-bg);
  padding: 16px 20px;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: var(--element-spacing);
  border: 1px solid var(--color-border-light);
  font-size: 12px;
  line-height: 1.5;
}

pre code {
  background: none;
  padding: 0;
  border-radius: 0;
}

/* ====== Tables ====== */
table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: var(--element-spacing);
  font-size: var(--font-size-body);
}

thead th {
  background: var(--color-bg-secondary);
  padding: 10px 12px;
  text-align: left;
  font-weight: var(--font-weight-semibold);
  border-bottom: 2px solid var(--color-border);
  font-size: var(--font-size-small);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
}

tbody td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
}

tbody tr:nth-child(even) {
  background: var(--color-bg-secondary);
}

/* ====== Callouts ====== */
.callout {
  padding: 12px 16px;
  margin-bottom: var(--element-spacing);
  border-radius: 8px;
  border-left: 4px solid var(--color-accent);
  background: var(--color-bg-secondary);
}

.callout-warning {
  border-left-color: var(--color-warning);
  background: #fff8e6;
}

.callout-tip {
  border-left-color: var(--color-success);
  background: #e8f8ee;
}

.callout-title {
  font-weight: var(--font-weight-semibold);
  margin-bottom: 4px;
  font-size: var(--font-size-small);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
}

/* ====== Horizontal Rule ====== */
hr {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: var(--section-spacing) 0;
}

/* ====== Page Break Utilities ====== */
.page-break {
  page-break-before: always;
}

.page-break-avoid {
  page-break-inside: avoid;
}

/* ====== Section Spacer ====== */
.section {
  margin-top: var(--section-spacing);
}

/* ====== Text Utilities ====== */
.text-lead {
  font-size: 18px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

.text-caption {
  font-size: var(--font-size-caption);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
}

.text-center {
  text-align: center;
}
```

- [ ] **Step 2: Verify no syntax errors**

The file should be parseable CSS. Run a quick sanity check by reading the file back.

- [ ] **Step 3: Commit**

```bash
git add templates/shared/base.css
git commit -m "feat: complete premium PDF design system in base.css"
```

---

### Task 7: Upgrade theme CSS files

**Files:**
- Modify: `templates/shared/themes/luxury-dark.css`
- Modify: `templates/shared/themes/editorial.css`
- Modify: `templates/shared/themes/minimal.css`

- [ ] **Step 1: Rewrite luxury-dark.css**

```css
:root {
  /* Typography */
  --font-heading: 'Playfair Display', Georgia, 'Times New Roman', serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

  /* Colors */
  --color-text-primary: #f5f5f7;
  --color-text-secondary: #a1a1a6;
  --color-text-muted: #6e6e73;
  --color-bg-primary: #1d1d1f;
  --color-bg-secondary: #2d2d2f;
  --color-accent: #d4af37;
  --color-accent-hover: #bfa030;
  --color-border: #333336;
  --color-border-light: #2a2a2c;
  --color-code-bg: #2d2d2f;
  --color-quote-border: #d4af37;

  /* Headings */
  --font-size-h1: 42px;
  --font-size-h2: 28px;
}

h1, h2, h3, h4 {
  font-weight: 700;
  letter-spacing: 0;
}

.cover-accent {
  background: linear-gradient(90deg, #d4af37, #f5d060);
}

.callout {
  background: #2d2d2f;
  border-left-color: #d4af37;
}

.callout-warning {
  background: #3d3520;
  border-left-color: #ff9f0a;
}

.callout-tip {
  background: #203d28;
  border-left-color: #30d158;
}

blockquote {
  background: #2d2d2f;
}
```

- [ ] **Step 2: Rewrite editorial.css**

```css
:root {
  /* Typography */
  --font-heading: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-body: 'Times New Roman', Times, Georgia, serif;
  --font-mono: 'Courier New', Courier, monospace;

  /* Colors */
  --color-text-primary: #111111;
  --color-text-secondary: #444444;
  --color-text-muted: #666666;
  --color-bg-primary: #fcfcfc;
  --color-bg-secondary: #f5f3f0;
  --color-accent: #b22222;
  --color-accent-hover: #8b1a1a;
  --color-border: #dddddd;
  --color-border-light: #e8e8e8;
  --color-code-bg: #f5f3f0;
  --color-quote-border: #b22222;

  /* Layout */
  --section-spacing: 40px;
}

h1, h2, h3, h4 {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

h1 {
  font-size: 30px;
  border-bottom: 3px solid var(--color-accent);
}

.cover-accent {
  background: var(--color-accent);
  height: 3px;
}

.cover-title {
  font-family: var(--font-heading);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 44px;
}
```

- [ ] **Step 3: Rewrite minimal.css**

```css
:root {
  /* Typography */
  --font-heading: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-body: 'Helvetica Neue', Helvetica, Arial, sans-serif;

  /* Colors */
  --color-text-primary: #000000;
  --color-text-secondary: #555555;
  --color-text-muted: #999999;
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f8f8f8;
  --color-accent: #000000;
  --color-accent-hover: #333333;
  --color-border: #eeeeee;
  --color-border-light: #f4f4f4;
  --color-code-bg: #f8f8f8;
  --color-quote-border: #000000;

  --font-weight-bold: 400;
  --font-weight-semibold: 400;
  --letter-spacing-tight: 0.05em;
  --letter-spacing-wide: 0.1em;
}

h1, h2, h3, h4 {
  font-weight: 300;
  letter-spacing: 0.05em;
}

h1 {
  font-size: 28px;
  border-bottom: 1px solid var(--color-border);
}

.cover-accent {
  background: var(--color-accent);
  width: 40px;
  height: 2px;
}

.cover-title {
  font-weight: 200;
  letter-spacing: 0.08em;
}
```

- [ ] **Step 4: Commit**

```bash
git add templates/shared/themes/
git commit -m "feat: upgrade theme CSS with full design tokens"
```

---

### Task 8: Update basic_doc.html.j2 with cover + TOC

**Files:**
- Modify: `templates/shared/basic_doc.html.j2`
- Create: `templates/shared/toc.html.j2`
- Create: `templates/shared/header_footer.html.j2`

- [ ] **Step 1: Create TOC partial template**

`templates/shared/toc.html.j2`:

```jinja2
{% if toc_items %}
<div class="toc">
  <h2>Table of Contents</h2>
  <ul class="toc-list">
  {% for item in toc_items %}
    <li class="toc-item toc-item-{{ item.level }}">
      <a href="#{{ item.id }}">{{ item.title }}</a>
      <span class="toc-page">{{ item.page }}</span>
    </li>
  {% endfor %}
  </ul>
</div>
{% endif %}
```

- [ ] **Step 2: Rewrite basic_doc.html.j2**

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        {% include 'shared/base.css' %}
    </style>
</head>
<body>
    <div class="page">
        <!-- Cover Page -->
        <div class="cover">
            <div class="cover-accent"></div>
            <div class="cover-title">{{ title }}</div>
            <div class="cover-subtitle">{{ subtitle if subtitle else niche }}</div>
            <div class="cover-meta">
                <span>Product: {{ product_type }}</span>
                <span>Date: {{ date }}</span>
            </div>
        </div>

        <!-- Table of Contents -->
        {% include 'shared/toc.html.j2' %}

        <!-- Content -->
        <div class="content">
            {{ content | safe }}
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 3: Update render_agent.py to pass new variables**

Add to `template_vars` dict in `render_agent.py`:

```python
import os
import json
import logging
import markdown
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from renderers.base import Renderer

logger = logging.getLogger(__name__)

def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        renderer: Renderer = context.get("renderer")
        if not renderer:
            raise ValueError("Renderer instance not injected into context")

        if not component.template:
            raise ValueError("No template specified for render_agent")

        html_content = ""
        mermaid_src = ""

        md_file = context.get(component.depends_on[0]) if component.depends_on else context.get("report")
        if md_file and md_file.endswith(".md") and os.path.exists(md_file):
            with open(md_file, "r") as f:
                md_text = f.read()

            # If format is "guide", generate shorter PDF-friendly version
            if getattr(component, "format", "full") == "guide":
                guide_prompt = (
                    f"Rewrite the following document as a concise, actionable guide "
                    f"focused on 'how to use, what to do, why to do it'. "
                    f"Keep it under 1000 words. Make it skimmable with bold key points.\n\n{md_text[:5000]}"
                )
                from .llm_client import generate_text
                md_text = generate_text(guide_prompt)

            html_content = markdown.markdown(md_text, extensions=['extra', 'toc'])

        if md_file and md_file.endswith(".mmd") and os.path.exists(md_file):
            with open(md_file, "r") as f:
                mermaid_src = f.read()

        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template(component.template)

        template_vars = {
            "title": job_spec.display_name or job_spec.niche,
            "subtitle": getattr(job_spec, "niche", ""),
            "niche": job_spec.niche,
            "product_type": job_spec.product_type.replace("_", " ").title(),
            "date": datetime.now().strftime("%B %d, %Y"),
            "content": html_content,
            "mermaid_src": mermaid_src,
            "theme": getattr(job_spec, "theme", "default"),
            "toc_items": [],
        }

        # Load catalog if available
        if "catalog" in context:
            with open(context["catalog"], "r") as cf:
                catalog_data = json.load(cf)
            if "images" in context:
                images_dir = os.path.abspath(context["images"])
                for i, item in enumerate(catalog_data):
                    item["image_path"] = os.path.join(images_dir, f"image_{i+1}.png").replace('\\', '/')
            template_vars["catalog"] = catalog_data

        final_html = template.render(**template_vars)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        renderer.render_pdf(final_html, output_path)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Render agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add templates/shared/basic_doc.html.j2 templates/shared/toc.html.j2 templates/shared/header_footer.html.j2 agents/render_agent.py
git commit -m "feat: premium PDF layout with cover, TOC, and format-aware content"
```

---

### Task 9: Upgrade product-specific templates

**Files:**
- Modify: `templates/research_pack/report.html.j2`
- Modify: `templates/visual_pack/reference_board.html.j2`
- Modify: `templates/visual_pack/showcase.html.j2`
- Modify: `templates/workflow_kit/diagram.html.j2`

- [ ] **Step 1: Rewrite report.html.j2**

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        {% include 'shared/base.css' %}
    </style>
</head>
<body>
    <div class="page">
        <div class="cover">
            <div class="cover-accent"></div>
            <div class="cover-title">{{ title }}</div>
            <div class="cover-subtitle">Research Report — {{ subtitle }}</div>
            <div class="cover-meta">
                <span>Product: {{ product_type }}</span>
                <span>Date: {{ date }}</span>
            </div>
        </div>

        {% include 'shared/toc.html.j2' %}

        <div class="content">
            {{ content | safe }}
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 2: Update reference_board.html.j2**

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} — Reference Board</title>
    <style>
        {% include 'shared/base.css' %}
        .grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin-top: 24px;
        }
        .card {
            border: 1px solid var(--color-border);
            padding: 16px;
            border-radius: 12px;
            page-break-inside: avoid;
            background: var(--color-bg-secondary);
        }
        .card img {
            width: 100%;
            height: auto;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .card-title {
            font-family: var(--font-heading);
            font-weight: var(--font-weight-semibold);
            font-size: 16px;
            margin-bottom: 4px;
        }
        .card-desc {
            font-size: 12px;
            color: var(--color-text-muted);
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="cover">
            <div class="cover-accent"></div>
            <div class="cover-title">Reference Board</div>
            <div class="cover-subtitle">{{ title }}</div>
            <div class="cover-meta">
                <span>Product: {{ product_type }}</span>
                <span>Date: {{ date }}</span>
            </div>
        </div>
        <p class="text-lead">A curated collection of visual references generated for this pack.</p>

        <div class="grid">
            {% for item in catalog %}
            <div class="card">
                <img src="file:///{{ item.image_path }}" alt="{{ item.title }}" />
                <div class="card-title">{{ item.title }}</div>
                <div class="card-desc">{{ item.description }}</div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 3: Update showcase.html.j2**

Same as current but update CSS variables to use new names (`--color-bg-primary` instead of literal `#000`, etc.):

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} — Showcase</title>
    <style>
        {% include 'shared/base.css' %}
        .showcase-page {
            width: 210mm;
            height: 297mm;
            position: relative;
            page-break-after: always;
            margin: 0 auto;
        }
        .showcase-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .overlay {
            position: absolute;
            bottom: 40px;
            left: 40px;
            right: 40px;
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(8px);
            padding: 24px 32px;
            border-radius: 16px;
        }
        .overlay-title {
            font-family: var(--font-heading);
            font-size: 24px;
            font-weight: var(--font-weight-semibold);
            margin-bottom: 8px;
        }
        .overlay-desc {
            font-size: 14px;
            color: var(--color-text-secondary);
        }
    </style>
</head>
<body style="background: #000; padding:0; margin:0;">
    {% for item in catalog %}
    <div class="showcase-page">
        <img class="showcase-img" src="file:///{{ item.image_path }}" alt="{{ item.title }}" />
        <div class="overlay">
            <div class="overlay-title">{{ item.title }}</div>
            <div class="overlay-desc">{{ item.description }}</div>
        </div>
    </div>
    {% endfor %}
</body>
</html>
```

- [ ] **Step 4: Update diagram.html.j2**

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} — Workflow Diagram</title>
    <style>
        {% include 'shared/base.css' %}
        .diagram-container {
            margin-top: 40px;
            display: flex;
            justify-content: center;
            background: var(--color-bg-secondary);
            padding: 32px;
            border-radius: 12px;
            border: 1px solid var(--color-border);
        }
        pre.mermaid {
            font-family: var(--font-mono);
            font-size: 12px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="cover">
            <div class="cover-accent"></div>
            <div class="cover-title">Workflow Diagram</div>
            <div class="cover-subtitle">{{ title }}</div>
            <div class="cover-meta">
                <span>Product: {{ product_type }}</span>
                <span>Date: {{ date }}</span>
            </div>
        </div>

        <p class="text-lead">A high-level view of the automated processes.</p>

        <div class="diagram-container">
            <pre class="mermaid">
{{ mermaid_src | safe }}
            </pre>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
    </script>
</body>
</html>
```

- [ ] **Step 5: Commit**

```bash
git add templates/research_pack/report.html.j2 templates/visual_pack/ templates/workflow_kit/
git commit -m "feat: upgrade all product templates with new design system"
```

---

### Task 10: Notion Agent v2 — Database creation with properties/relations

**Files:**
- Create: `agents/notion_schema_agent.py`
- Modify: `agents/notion_agent.py`
- Modify: `agents/registry.py`
- Modify: `schemas/operating_system.json` (wire new notion components)

- [ ] **Step 1: Create notion_schema_agent.py**

```python
import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"

SCHEMA_PROMPT = """You are a Notion database architect specializing in {niche}.

Design a complete Notion workspace blueprint for a "{niche}" professional or team.

Generate a JSON object with a 'databases' array. Each database has:

{{
  "databases": [
    {{
      "name": "Database Name",
      "description": "What this database tracks",
      "icon": "emoji (e.g. 📁)",
      "properties": {{
        "Property Name": {{"type": "title", "options": []}},
        "Status": {{"type": "select", "options": ["Option 1", "Option 2", "Option 3"]}},
        "Date": {{"type": "date"}},
        "Related": {{"type": "relation", "target": "Other Database Name"}},
        "Formula": {{"type": "formula", "expression": "prop(\\"Property Name\\")"}},
        "Number": {{"type": "number", "format": "number"}},
        "URL": {{"type": "url"}},
        "Email": {{"type": "email"}},
        "Phone": {{"type": "phone"}},
        "Checkbox": {{"type": "checkbox"}},
        "Files": {{"type": "files"}}
      }}
    }}
  ]
}}

Supported property types: title, text, number, select, multi_select, date, person, files, checkbox, url, email, phone, formula, relation, rollup, created_time, created_by, last_edited_time, last_edited_by, status

Relations: use 'target' field to match database name. Use 'type': 'rollup' with 'rollup_property', 'rollup_function' for rollups.

Create 3-5 databases that form a connected system. Use relations to link them.

Return ONLY raw JSON — no markdown, no explanation, no code block wrapping.
"""


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        prompt = SCHEMA_PROMPT.format(niche=job_spec.niche)

        # Include context from content components for richer schema
        context_text = ""
        for dep in component.depends_on:
            dep_path = context.get(dep)
            if dep_path and os.path.exists(dep_path):
                with open(dep_path, "r") as f:
                    excerpt = f.read()[:2000]
                context_text += f"\n\nContent from {dep}:\n{excerpt[:2000]}"

        if context_text:
            prompt += f"\n\nUse this context to inform the database design:\n{context_text}"

        content = generate_text(prompt)

        # Clean potential markdown wrapping
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        # Validate JSON
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            return AgentResult(status="failed", error=f"Invalid schema JSON: {e}")

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion schema agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Rewrite notion_agent.py**

```python
import os
import json
import time
import logging
from typing import Dict, List, Any

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

NOTION_PROPERTY_CREATORS = {
    "title": lambda config: {"title": {}},
    "text": lambda config: {"rich_text": {}},
    "number": lambda config: {"number": {"format": config.get("format", "number")}},
    "select": lambda config: {"select": {"options": [{"name": o, "color": "default"} for o in config.get("options", [])]}},
    "multi_select": lambda config: {"multi_select": {"options": [{"name": o, "color": "default"} for o in config.get("options", [])]}},
    "date": lambda config: {"date": {}},
    "person": lambda config: {"people": {}},
    "files": lambda config: {"files": {}},
    "checkbox": lambda config: {"checkbox": {}},
    "url": lambda config: {"url": {}},
    "email": lambda config: {"email": {}},
    "phone": lambda config: {"phone": {}},
    "formula": lambda config: {"formula": {"expression": config.get("expression", "")}},
    "created_time": lambda config: {"created_time": {}},
    "created_by": lambda config: {"created_by": {}},
    "last_edited_time": lambda config: {"last_edited_time": {}},
    "last_edited_by": lambda config: {"last_edited_by": {}},
    "status": lambda config: {"status": {"options": [{"name": o, "color": "default"} for o in config.get("options", ["Not started", "In progress", "Done"])]}},
}


def _build_property_config(properties: Dict) -> Dict:
    """Convert blueprint properties to Notion API property configs."""
    config = {}
    for name, prop_config in properties.items():
        prop_type = prop_config["type"]
        creator = NOTION_PROPERTY_CREATORS.get(prop_type)
        if creator:
            config[name] = creator(prop_config)
        else:
            config[name] = {"rich_text": {}}
    return config


def _resolve_relations(blueprint: Dict, db_id_map: Dict[str, str]) -> Dict:
    """Replace relation target names with actual database IDs."""
    relation_configs = {}
    for db in blueprint.get("databases", []):
        db_name = db["name"]
        if db_name not in db_id_map:
            continue
        for prop_name, prop_config in db.get("properties", {}).items():
            if prop_config["type"] == "relation":
                target_name = prop_config.get("target", "")
                target_id = db_id_map.get(target_name)
                if target_id:
                    relation_configs[f"{db_name}.{prop_name}"] = {
                        "db_id": db_id_map[db_name],
                        "prop_name": prop_name,
                        "target_id": target_id,
                    }
    return relation_configs


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        notion_api_key = os.getenv("NOTION_API_KEY")
        notion_parent_id = os.getenv("NOTION_PARENT_PAGE_ID")

        if not notion_api_key or not notion_parent_id:
            logger.warning("Notion API Key or Parent Page ID not configured. Skipping notion sync.")
            return AgentResult(status="skipped", error="Notion not configured")

        from notion_client import Client
        from notion_client.errors import APIResponseError
        notion = Client(auth=notion_api_key)

        # Look for schema blueprint from notion_schema_agent
        blueprint_path = context.get("notion_schema")
        if not blueprint_path or not os.path.exists(blueprint_path):
            # Fallback: look for any component with format=notion
            for key, path in context.items():
                if path and os.path.exists(path) and path.endswith(".json"):
                    with open(path, "r") as f:
                        try:
                            data = json.load(f)
                            if "databases" in data:
                                blueprint_path = path
                                break
                        except json.JSONDecodeError:
                            continue

        if not blueprint_path:
            return AgentResult(status="failed", error="No Notion schema blueprint found in context")

        with open(blueprint_path, "r") as f:
            blueprint = json.load(f)

        # Create root page
        root_page = notion.pages.create(
            parent={"page_id": notion_parent_id},
            properties={
                "title": {
                    "title": [{"text": {"content": f"{job_spec.niche} ({job_spec.product_type})"}}]
                }
            }
        )
        root_page_id = root_page["id"]
        root_page_url = root_page.get("url", f"https://notion.so/{root_page_id.replace('-', '')}")

        sync_result = {
            "root_page_id": root_page_id,
            "root_page_url": root_page_url,
            "databases": {},
        }

        # Phase 1: Create all databases first
        db_id_map: Dict[str, str] = {}
        for db in blueprint.get("databases", []):
            db_name = db["name"]
            try:
                properties = _build_property_config(db.get("properties", {}))
                new_db = notion.databases.create(
                    parent={"page_id": root_page_id},
                    title=[{"type": "text", "text": {"content": db_name}}],
                    properties=properties,
                    description=db.get("description", ""),
                )
                db_id_map[db_name] = new_db["id"]
                logger.info(f"Created database: {db_name} -> {new_db['id']}")
            except Exception as e:
                logger.error(f"Failed to create database {db_name}: {e}")

        # Phase 2: Add relations (need all DB IDs first)
        relation_configs = _resolve_relations(blueprint, db_id_map)
        if relation_configs:
            for key, config in relation_configs.items():
                try:
                    notion.databases.update(
                        database_id=config["db_id"],
                        properties={
                            config["prop_name"]: {
                                "type": "relation",
                                "relation": {"database_id": config["target_id"]},
                            }
                        },
                    )
                    logger.info(f"Set relation: {key}")
                except Exception as e:
                    logger.error(f"Failed to set relation {key}: {e}")

        # Phase 3: Create view configurations if specified
        for db in blueprint.get("databases", []):
            db_name = db["name"]
            db_id = db_id_map.get(db_name)
            if not db_id:
                continue
            views = db.get("views", [])
            for view in views:
                try:
                    view_type = view.get("type", "table")
                    view_name = view.get("name", "Default View")
                    filters = view.get("filters", [])

                    # Notion API doesn't have a direct create-view endpoint
                    # Views are created via database update with view properties
                    logger.info(f"View {view_name} ({view_type}) would be set on {db_name} — requires manual UI or Notion API query/database endpoint")
                except Exception as e:
                    logger.warning(f"Failed to configure view {view.get('name', 'unknown')}: {e}")

        # Create a Notion template link page
        template_page = notion.pages.create(
            parent={"page_id": root_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": "📋 Notion Template — How to Use"}}]
                }
            }
        )

        # Add usage instructions as blocks
        instructions = [
            {"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": "Welcome to Your New Workspace"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"This Notion workspace was generated for: {job_spec.niche}"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Each database below is pre-configured with the properties, relations, and views you need."}}]}},
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Databases in this workspace"}}]}},
        ]

        for db in blueprint.get("databases", []):
            db_name = db["name"]
            db_desc = db.get("description", "")
            instructions.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": f"**{db_name}** — {db_desc}"}}]},
            })

        instructions.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "How to use this template"}}]},
        })

        usage_steps = [
            "Click the 'Duplicate' button in the top-right corner of this page.",
            "The entire workspace will copy to your personal Notion account.",
            "Customize the databases, add your own data, and modify properties as needed.",
            "Share individual databases or the whole workspace with your team.",
        ]
        for step in usage_steps:
            instructions.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"text": {"content": step}}]},
            })

        # Append in chunks
        for i in range(0, len(instructions), 100):
            chunk = instructions[i:i + 100]
            retries = 3
            for attempt in range(retries):
                try:
                    notion.blocks.children.append(block_id=template_page["id"], children=chunk)
                    break
                except APIResponseError as e:
                    if e.status == 429 and attempt < retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        logger.error(f"Failed to append blocks: {e}")
                        break

        sync_result["databases"] = db_id_map
        sync_result["template_page_id"] = template_page["id"]
        sync_result["template_page_url"] = template_page.get("url", "")

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(sync_result, f, indent=2)

        # Also generate a Notion_Template_Link.md for the zip
        link_dir = os.path.join("outputs", job_spec.slug, "presentation")
        os.makedirs(link_dir, exist_ok=True)
        link_path = os.path.join(link_dir, "Notion_Template_Link.md")
        with open(link_path, "w") as f:
            f.write(f"# Notion Template Access Link\n\n")
            f.write(f"Your interactive Notion workspace has been successfully created!\n\n")
            f.write(f"## 🔗 [Click here to open the Notion Template]({root_page_url})\n\n")
            f.write(f"### How to use this template:\n")
            f.write(f"1. Open the link above in your browser (make sure you are logged into your Notion account).\n")
            f.write(f"2. Click the **'Duplicate'** button in the top-right corner of the page.\n")
            f.write(f"3. The workspace will copy directly into your own Notion account, ready to be customized or sold!\n")

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 3: Update registry.py**

Add notion_schema_agent to the registry:

```python
from . import (
    research_agent,
    csv_export_agent,
    content_agent,
    render_agent,
    packaging_agent,
    notion_agent,
    catalog_agent,
    visual_agent,
    diagram_agent,
    notion_schema_agent
)

AGENT_REGISTRY = {
    "research_agent": research_agent.run,
    "csv_export_agent": csv_export_agent.run,
    "content_agent": content_agent.run,
    "render_agent": render_agent.run,
    "packaging_agent": packaging_agent.run,
    "notion_agent": notion_agent.run,
    "catalog_agent": catalog_agent.run,
    "visual_agent": visual_agent.run,
    "diagram_agent": diagram_agent.run,
    "notion_schema_agent": notion_schema_agent.run,
}
```

- [ ] **Step 4: Add notion_schema component to schemas**

In `operating_system.json`, add `notion_schema` component before `notion_tree`:

```json
{
  "id": "notion_schema",
  "agent": "notion_schema_agent",
  "output": "data/notion_schema.json",
  "depends_on": ["guide", "sops", "templates", "prompts"]
},
```

And update `notion_tree` to depend on `notion_schema`:
```json
{
  "id": "notion_tree",
  "agent": "notion_agent",
  "output": "notion_sync.json",
  "depends_on": ["notion_schema"]
}
```

- [ ] **Step 5: Commit**

```bash
git add agents/notion_schema_agent.py agents/notion_agent.py agents/registry.py schemas/operating_system.json
git commit -m "feat: Notion v2 with database creation, properties, relations, and share URLs"
```

---

### Task 11: Run existing tests to verify nothing is broken

**Files:**
- Run: `tests/test_orchestrator.py`
- Run: `tests/test_agents.py`

- [ ] **Step 1: Run orchestrator tests**

```bash
python -m pytest tests/test_orchestrator.py -v
```
Expected: Tests pass (topological sort, etc.)

- [ ] **Step 2: Run agent tests**

```bash
python -m pytest tests/test_agents.py -v
```
Expected: Existing tests pass (note: some may be skipped due to API keys)

- [ ] **Step 3: If any tests fail, fix them**

Check failure output and adjust imports or references as needed.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: fix tests after system upgrade"
```
