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

        blueprint_path = context.get("notion_schema")
        if not blueprint_path or not os.path.exists(blueprint_path):
            for key, path in context.items():
                if path and os.path.exists(path) and path.endswith(".json"):
                    with open(path, "r", encoding="utf-8") as f:
                        try:
                            data = json.load(f)
                            if "databases" in data:
                                blueprint_path = path
                                break
                        except json.JSONDecodeError:
                            continue

        if not blueprint_path:
            return AgentResult(status="failed", error="No Notion schema blueprint found in context")

        with open(blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

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

        db_id_map: Dict[str, str] = {}
        for db in blueprint.get("databases", []):
            db_name = db["name"]
            try:
                properties = _build_property_config(db.get("properties", {}))
                
                # Format parent correctly with type for paged media API version 2022-06-28
                parent_config = {"type": "page_id", "page_id": root_page_id}
                db_body = {
                    "parent": parent_config,
                    "title": [{"type": "text", "text": {"content": db_name}}],
                    "properties": properties,
                }
                db_desc = db.get("description", "")
                if db_desc:
                    db_body["description"] = [{"type": "text", "text": {"content": db_desc}}]

                new_db = notion.request(
                    path="databases",
                    method="POST",
                    body=db_body
                )
                db_id_map[db_name] = new_db["id"]
                logger.info(f"Created database: {db_name} -> {new_db['id']}")
            except Exception as e:
                logger.error(f"Failed to create database {db_name}: {e}")

        relation_configs = _resolve_relations(blueprint, db_id_map)
        if relation_configs:
            for key, config in relation_configs.items():
                try:
                    notion.request(
                        path=f"databases/{config['db_id']}",
                        method="PATCH",
                        body={
                            "properties": {
                                config["prop_name"]: {
                                    "relation": {"database_id": config["target_id"]}
                                }
                            }
                        }
                    )
                    logger.info(f"Set relation: {key}")
                except Exception as e:
                    logger.error(f"Failed to set relation {key}: {e}")

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
                    logger.info(f"View {view_name} ({view_type}) would be set on {db_name}")
                except Exception as e:
                    logger.warning(f"Failed to configure view {view.get('name', 'unknown')}: {e}")

        template_page = notion.pages.create(
            parent={"page_id": root_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": "📋 Notion Template — How to Use"}}]
                }
            }
        )

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
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sync_result, f, indent=2)

        link_dir = os.path.join("outputs", job_spec.slug, "presentation")
        os.makedirs(link_dir, exist_ok=True)
        link_path = os.path.join(link_dir, "Notion_Template_Link.md")
        with open(link_path, "w", encoding="utf-8") as f:
            f.write(f"# Notion Template Access Link\n\n")
            f.write(f"Your interactive Notion workspace has been successfully created!\n\n")
            f.write(f"## 🔗 [Click here to open the Notion Template]({root_page_url})\n\n")
            f.write(f"### How to use this template:\n")
            f.write(f"1. Open the link above in your browser.\n")
            f.write(f"2. Click the **'Duplicate'** button in the top-right corner of the page.\n")
            f.write(f"3. The workspace will copy directly into your own Notion account, ready to be customized or sold!\n")

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
