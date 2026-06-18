import os
import json
from datetime import datetime, timezone
import typer
import re

from dotenv import load_dotenv, set_key


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def run_wizard() -> str | None:
    print("Welcome to the Digital Product Factory")
    print("--------------------------------------")

    # Check .env
    load_dotenv()
    env_path = ".env"

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = typer.prompt("Anthropic API Key missing. Please enter it")
        set_key(env_path, "ANTHROPIC_API_KEY", api_key)

    product_type = "discovery"

    niche = typer.prompt("What is the niche/topic?")

    default_display = niche.title()
    display_name = typer.prompt("Display name for the product", default=default_display)

    default_slug = slugify(niche)
    slug = typer.prompt("Output slug", default=default_slug)

    print("\nAvailable Themes:")
    print("1. Default — Clean, professional, versatile. Good for most products.")
    print("2. Luxury Dark — Premium dark theme with gold accents. For high-ticket products.")
    print("3. Editorial — Magazine-style with large typography. For content-heavy reports.")
    print("4. Minimal — Sparse, elegant. For design-forward products.")
    theme_choice = typer.prompt("Select a theme (1, 2, 3, or 4)", default="1")
    if theme_choice.strip() == "4":
        theme = "minimal"
    elif theme_choice.strip() == "3":
        theme = "editorial"
    elif theme_choice.strip() == "2":
        theme = "luxury-dark"
    else:
        theme = "default"

    notion_sync = False
    notion_parent_page_id = None

    sync = typer.prompt(
        "Do you want to sync this to Notion? (y/n)", default="y"
    )
    if sync.lower() == "y":
        notion_sync = True

        notion_api_key = os.getenv("NOTION_API_KEY")
        if not notion_api_key or notion_api_key == "your_notion_api_key_here":
            notion_api_key = typer.prompt(
                "Notion API Key missing. Please enter it"
            )
            set_key(env_path, "NOTION_API_KEY", notion_api_key)

        notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
        if (
            not notion_parent_page_id
            or notion_parent_page_id == "your_notion_parent_page_id_here"
        ):
            notion_parent_page_id = typer.prompt(
                "Notion Parent Page ID missing. Please enter it"
            )
            set_key(env_path, "NOTION_PARENT_PAGE_ID", notion_parent_page_id)

    notion_only = False
    if not notion_sync:
        notion_only_prompt = typer.prompt(
            "Notion-only template bechein? (y/n)", default="n"
        )
        if notion_only_prompt.lower() == "y":
            notion_only = True
            notion_sync = True  # standalone mode requires notion sync
            notion_api_key = os.getenv("NOTION_API_KEY")
            if not notion_api_key or notion_api_key == "your_notion_api_key_here":
                notion_api_key = typer.prompt("Notion API Key missing. Please enter it")
                set_key(env_path, "NOTION_API_KEY", notion_api_key)
            notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
            if (
                not notion_parent_page_id
                or notion_parent_page_id == "your_notion_parent_page_id_here"
            ):
                notion_parent_page_id = typer.prompt(
                    "Notion Parent Page ID missing. Please enter it"
                )
                set_key(env_path, "NOTION_PARENT_PAGE_ID", notion_parent_page_id)

    from channels import CHANNEL_REGISTRY

    channel_configs = []

    print("\nAvailable Channels:")
    channel_names = list(CHANNEL_REGISTRY.keys())
    for i, ch_name in enumerate(channel_names, 1):
        print(f"  {i}. {ch_name.title()}")

    while True:
        selected = typer.prompt(
            "Which channels to publish to? (comma-separated numbers, e.g. '1,2', or 'all')",
            default="1",
        )
        if selected.strip().lower() == "all":
            selected_indices = list(range(len(channel_names)))
            break
        parts = [p.strip() for p in selected.split(",")]
        valid = True
        indices = []
        for part in parts:
            if not part.isdigit():
                valid = False
                break
            idx = int(part) - 1
            if idx < 0 or idx >= len(channel_names):
                valid = False
                break
            indices.append(idx)
        if valid:
            selected_indices = indices
            break
        print(f"Invalid input. Enter comma-separated numbers 1-{len(channel_names)}, or 'all'.")

    for i, ch_name in enumerate(channel_names):
        if i in selected_indices:
            channel_configs.append({
                "name": ch_name,
                "enabled": True,
                "config": {},
            })
            if ch_name == "gumroad":
                gumroad_token = os.getenv("GUMROAD_ACCESS_TOKEN")
                if not gumroad_token:
                    gumroad_token = typer.prompt("Enter your Gumroad access token")
                    set_key(env_path, "GUMROAD_ACCESS_TOKEN", gumroad_token)

    if any(c["name"] == "gumroad" for c in channel_configs):
        validate_market = typer.prompt(
            "Would you like to validate your product type against Gumroad market data? (y/n)",
            default="n",
        )
        if validate_market.lower() == "y":
            print(
                "Market validation will run during pipeline execution as part of the gumroad_research component."
            )

    if product_type == "visual_pack":
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key == "your_openai_api_key_here":
            print("\nNotice: OPENAI_API_KEY is not set.")
            use_placeholder = typer.prompt(
                "Do you want to use dummy placeholders instead of real images? (y/n)",
                default="y",
            )
            if use_placeholder.lower() != "y":
                openai_key = typer.prompt("Please enter your OpenAI API Key")
                set_key(env_path, "OPENAI_API_KEY", openai_key)

    landing_page_enabled = False
    social_promotion_enabled = False
    cta_text = ""

    landing_prompt = typer.prompt("\nLanding page bhi banayein? (y/n)", default="n")
    if landing_prompt.lower() == "y":
        landing_page_enabled = True

        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            gemini_key = typer.prompt("Gemini API Key (for image generation)")
            set_key(env_path, "GEMINI_API_KEY", gemini_key)

        vercel_token = os.getenv("VERCEL_TOKEN")
        if not vercel_token:
            vercel_token = typer.prompt("Vercel Token (for deployment)")
            set_key(env_path, "VERCEL_TOKEN", vercel_token)

        cta_text = typer.prompt(
            "Call-to-action text for landing page", default="Buy Now on Gumroad"
        )

        social_prompt = typer.prompt(
            "\nSocial media pe bhi share karein? (y/n)", default="n"
        )
        if social_prompt.lower() == "y":
            social_promotion_enabled = True

            fb_token = os.getenv("FACEBOOK_PAGE_TOKEN")
            if not fb_token:
                fb_token = typer.prompt("Facebook Page Access Token")
                set_key(env_path, "FACEBOOK_PAGE_TOKEN", fb_token)

            pin_token = os.getenv("PINTEREST_TOKEN")
            if not pin_token:
                pin_token = typer.prompt("Pinterest Access Token")
                set_key(env_path, "PINTEREST_TOKEN", pin_token)

    job_spec = {
        "slug": slug,
        "product_type": product_type,
        "niche": niche,
        "display_name": display_name,
        "theme": theme,
        "notion_sync": notion_sync,
        "notion_only": notion_only,
        "notion_parent_page_id": notion_parent_page_id,
        "channels": channel_configs,
        "landing_page_enabled": landing_page_enabled,
        "social_promotion_enabled": social_promotion_enabled,
        "call_to_action": cta_text,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # .env pre-validation
    missing_vars = []
    if landing_page_enabled:
        if not os.getenv("GEMINI_API_KEY"):
            missing_vars.append("GEMINI_API_KEY")
        if not os.getenv("VERCEL_TOKEN"):
            missing_vars.append("VERCEL_TOKEN")
    if social_promotion_enabled:
        if not os.getenv("FACEBOOK_PAGE_TOKEN"):
            missing_vars.append("FACEBOOK_PAGE_TOKEN")
    if any(c["name"] == "gumroad" for c in channel_configs):
        if not os.getenv("GUMROAD_ACCESS_TOKEN"):
            missing_vars.append("GUMROAD_ACCESS_TOKEN")

    if missing_vars:
        print(f"\nWarning: Missing environment variables: {', '.join(missing_vars)}")
        print("Pipeline may fail. Set them in .env and retry, or continue anyway.")
        proceed = typer.prompt("Continue? (y/n)", default="n")
        if proceed.lower() != "y":
            print("Aborted.")
            return None

    output_dir = os.path.join("outputs", slug)
    os.makedirs(output_dir, exist_ok=True)

    job_spec_path = os.path.join(output_dir, "job_spec.json")
    with open(job_spec_path, "w") as f:
        json.dump(job_spec, f, indent=2)

    print(f"\nJob spec written to {job_spec_path}")
    return job_spec_path
