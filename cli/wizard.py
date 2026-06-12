import os
import json
from datetime import datetime
import typer
import re

from dotenv import load_dotenv, set_key

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

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
        
    print("\nAvailable Product Types:")
    print("1. Research Pack (research_pack)")
    print("2. Operating System (operating_system)")
    print("3. Visual Pack (visual_pack)")
    print("4. Workflow Kit (workflow_kit)")
    
    choice = typer.prompt("Select a product type (1, 2, 3, or 4)", default="1")
    if choice.strip() == "4":
        product_type = "workflow_kit"
    elif choice.strip() == "3":
        product_type = "visual_pack"
    elif choice.strip() == "2":
        product_type = "operating_system"
    else:
        product_type = "research_pack"
    
    niche = typer.prompt("What is the niche/topic?")
    default_slug = slugify(niche)
    slug = typer.prompt("Output slug", default=default_slug)
    
    print("\nAvailable Themes:")
    print("1. Default")
    print("2. Luxury Dark (luxury-dark)")
    print("3. Editorial (editorial)")
    print("4. Minimal (minimal)")
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
    
    # Load schema to check if notion sync is supported
    schema_path = os.path.join("schemas", f"{product_type}.json")
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            schema = json.load(f)
            
        if schema.get("notion_sync"):
            sync = typer.prompt("Do you want to sync this to Notion? (y/n)", default="y")
            if sync.lower() == 'y':
                notion_sync = True
                
                notion_api_key = os.getenv("NOTION_API_KEY")
                if not notion_api_key or notion_api_key == "your_notion_api_key_here":
                    notion_api_key = typer.prompt("Notion API Key missing. Please enter it")
                    set_key(env_path, "NOTION_API_KEY", notion_api_key)
                    
                notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
                if not notion_parent_page_id or notion_parent_page_id == "your_notion_parent_page_id_here":
                    notion_parent_page_id = typer.prompt("Notion Parent Page ID missing. Please enter it")
                    set_key(env_path, "NOTION_PARENT_PAGE_ID", notion_parent_page_id)
                    
    if product_type == "visual_pack":
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key == "your_openai_api_key_here":
            print("\nNotice: OPENAI_API_KEY is not set.")
            use_placeholder = typer.prompt("Do you want to use dummy placeholders instead of real images? (y/n)", default="y")
            if use_placeholder.lower() != 'y':
                openai_key = typer.prompt("Please enter your OpenAI API Key")
                set_key(env_path, "OPENAI_API_KEY", openai_key)
    
    job_spec = {
        "slug": slug,
        "product_type": product_type,
        "niche": niche,
        "theme": theme,
        "notion_sync": notion_sync,
        "notion_parent_page_id": notion_parent_page_id,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    
    output_dir = os.path.join("outputs", slug)
    os.makedirs(output_dir, exist_ok=True)
    
    job_spec_path = os.path.join(output_dir, "job_spec.json")
    with open(job_spec_path, "w") as f:
        json.dump(job_spec, f, indent=2)
        
    print(f"\nJob spec written to {job_spec_path}")
    return job_spec_path
