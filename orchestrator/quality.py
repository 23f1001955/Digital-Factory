import re
import logging

logger = logging.getLogger(__name__)

# Known AI-ism patterns
AI_ISM_PATTERNS = [
    r"in today['']s digital (landscape|world|era|age)",
    r"in the ever-evolving (world|landscape|realm)",
    r"it['']s worth noting that",
    r"let['']s dive in",
    r"delve into",
    r"a myriad of",
    r"in this comprehensive (guide|article|post)",
    r"unlock the (power|potential|secret)",
    r"game-changer",
    r"revolutionize (your|the)",
    r"embark on (a|your) journey",
    r"are you tired of",
    r"look no further",
    r"unleash your",
    r"the power of",
    r"in the world of",
    r"It is important to note",
    r"as previously mentioned",
    r"in conclusion",
    r"to sum up",
    r"ultimately,?",
    r"in summary",
    r"when it comes to",
    r"it goes without saying",
    r"needless to say",
]

MIN_WORDS_BY_TYPE = {
    "full": 500,
    "guide": 300,
    "notion": 100,
    "prompt": 50,
    "resource": 100,
}


def check_word_count(content: str, format_type: str = "full") -> list:
    issues = []
    min_words = MIN_WORDS_BY_TYPE.get(format_type, 100)
    words = len(content.split())
    if words < min_words:
        issues.append({
            "category": "word_count",
            "severity": "error",
            "message": f"Only {words} words (minimum {min_words} for {format_type} format)",
        })
    elif words < min_words * 1.5:
        issues.append({
            "category": "word_count",
            "severity": "warning",
            "message": f"Only {words} words ({min_words} minimum) — consider expanding",
        })
    return issues


def check_headings(content: str) -> list:
    issues = []
    has_h1 = bool(re.search(r"^#\s+.+$", content, re.MULTILINE))
    if not has_h1:
        issues.append({
            "category": "headings",
            "severity": "error",
            "message": "No H1 heading found — content must start with # Title",
        })
    h2_count = len(re.findall(r"^##\s+.+$", content, re.MULTILINE))
    if h2_count == 0:
        issues.append({
            "category": "headings",
            "severity": "warning",
            "message": "No H2 headings — content lacks section structure",
        })
    return issues


def check_empty_sections(content: str) -> list:
    issues = []
    sections = re.split(r"\n(?=#+\s)", content)
    for section in sections:
        lines = [l for l in section.strip().split("\n") if l.strip()]
        heading = lines[0] if lines else ""
        body = [l for l in lines[1:] if not l.startswith("#")]
        body_text = " ".join(body).strip()
        if heading.startswith("#") and len(body_text.split()) < 5:
            issues.append({
                "category": "empty_section",
                "severity": "error",
                "message": f"Section '{heading.strip()}' has minimal content ({len(body_text.split())} words)",
            })
    return issues


def detect_ai_isms(content: str) -> list:
    issues = []
    for pattern in AI_ISM_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            issues.append({
                "category": "ai_ism",
                "severity": "warning",
                "message": f"AI-ism pattern detected: '{match}'",
            })
    return issues


def check_format_compliance(content: str) -> list:
    issues = []
    lines = content.split("\n")
    in_code_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if re.match(r"^\[.+\]\(.*\)$", stripped):
            issues.append({
                "category": "format_error",
                "severity": "warning",
                "message": f"Possible broken link/text on line {i+1}: '{stripped[:80]}'",
            })
    return issues


def compute_score(issues: list) -> float:
    if not issues:
        return 1.0
    deductions = {
        "error": 0.25,
        "warning": 0.1,
        "info": 0.02,
    }
    score = 1.0
    for issue in issues:
        score -= deductions.get(issue["severity"], 0.05)
    return max(0.0, round(score, 2))


def run_quality_checks(content: str, format_type: str = "full") -> tuple:
    all_issues = []
    all_issues.extend(check_word_count(content, format_type))
    all_issues.extend(check_headings(content))
    all_issues.extend(check_empty_sections(content))
    all_issues.extend(detect_ai_isms(content))
    all_issues.extend(check_format_compliance(content))
    score = compute_score(all_issues)
    return score, all_issues
