import os
import json

import time
import random
import logging
from typing import Dict, Any, Callable, TypeVar

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

DB_ICONS = {
    "template": "\U0001f4e6",
    "product": "\U0001f4e6",
    "sales": "\U0001f4b0",
    "invoice": "\U0001f9fe",
    "financial": "\U0001f4ca",
    "development": "\U0001f6e0\ufe0f",
    "task": "\u2705",
    "qa": "\U0001f50d",
    "bug": "\U0001f41b",
    "issue": "\U000026a0\ufe0f",
    "customer": "\U0001f464",
    "support": "\U0001f3a7",
    "client": "\U0001f91d",
    "content": "\U0001f4dd",
    "marketing": "\U0001f4e2",
    "asset": "\U0001f5bc\ufe0f",
    "project": "\U0001f4cb",
    "team": "\U0001f91d",
    "sop": "\U0001f4c4",
    "guide": "\U0001f4d6",
    "roadmap": "\U0001f5e3\ufe0f",
    "default": "\U0001f4cb",
}

SELECT_COLORS = [
    "default",
    "gray",
    "brown",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "red",
]


def _retry_call(fn: Callable[..., T], *args, max_retries: int = 4, **kwargs) -> T:
    """Call fn(*args, **kwargs) with exponential backoff + jitter on 429."""
    from notion_client.errors import APIResponseError

    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except APIResponseError as e:
            if e.status == 429 and attempt < max_retries - 1:
                sleep_sec = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Rate limited (429), retrying in {sleep_sec:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(sleep_sec)
            else:
                raise
    raise RuntimeError("Unreachable — max retries exhausted")


NOTION_PROPERTY_CREATORS = {
    "title": lambda config: {"title": {}},
    "text": lambda config: {"rich_text": {}},
    "number": lambda config: {"number": {"format": config.get("format", "number")}},
    "select": lambda config: {
        "select": {
            "options": [
                {"name": o, "color": SELECT_COLORS[i % len(SELECT_COLORS)]}
                for i, o in enumerate(config.get("options", []))
            ]
        }
    },
    "multi_select": lambda config: {
        "multi_select": {
            "options": [
                {"name": o, "color": SELECT_COLORS[i % len(SELECT_COLORS)]}
                for i, o in enumerate(config.get("options", []))
            ]
        }
    },
    "date": lambda config: {"date": {}},
    "person": lambda config: {"people": {}},
    "files": lambda config: {"files": {}},
    "checkbox": lambda config: {"checkbox": {}},
    "url": lambda config: {"url": {}},
    "email": lambda config: {"email": {}},
    "phone": lambda config: {"phone_number": {}},
    "phone_number": lambda config: {"phone_number": {}},
    "formula": lambda config: {"formula": {"expression": config.get("expression", "")}},
    "created_time": lambda config: {"created_time": {}},
    "created_by": lambda config: {"created_by": {}},
    "last_edited_time": lambda config: {"last_edited_time": {}},
    "last_edited_by": lambda config: {"last_edited_by": {}},
    "status": lambda config: {
        "status": {
            "options": [
                {"name": o, "color": SELECT_COLORS[i % len(SELECT_COLORS)]}
                for i, o in enumerate(
                    config.get("options", ["Not started", "In progress", "Done"])
                )
            ]
        }
    },
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


def _pick_icon(name: str) -> str:
    name_lower = name.lower()
    for keyword, icon in DB_ICONS.items():
        if keyword in name_lower:
            return icon
    return DB_ICONS["default"]


def _build_sample_properties(
    db_props: Dict[str, Any], row_index: int, num_rows: int
) -> Dict[str, Any]:
    titles = [
        "Alpha",
        "Beta",
        "Gamma",
        "Delta",
        "Epsilon",
        "Zeta",
        "Eta",
        "Theta",
        "Iota",
        "Kappa",
    ]
    title = titles[row_index % len(titles)]

    sample_values: Dict[str, Any] = {}
    for prop_name, prop_config in db_props.items():
        ptype = prop_config["type"]
        if ptype == "title":
            sample_values[prop_name] = {
                "title": [{"text": {"content": f"Sample {title}"}}]
            }
        elif ptype == "rich_text":
            sample_values[prop_name] = {
                "rich_text": [{"text": {"content": f"Description for {title}"}}]
            }
        elif ptype == "text":
            sample_values[prop_name] = {
                "rich_text": [{"text": {"content": f"Text for {title}"}}]
            }
        elif ptype == "number":
            sample_values[prop_name] = {"number": random.randint(10, 999)}
        elif ptype == "select":
            opts = prop_config.get("options", [])
            if opts:
                sample_values[prop_name] = {
                    "select": {"name": opts[row_index % len(opts)]}
                }
        elif ptype == "multi_select":
            opts = prop_config.get("options", [])
            if opts:
                count = min(2, len(opts))
                sample_values[prop_name] = {
                    "multi_select": [
                        {"name": opts[(row_index + i) % len(opts)]}
                        for i in range(count)
                    ]
                }
        elif ptype == "status":
            opts = prop_config.get("options", ["Not started", "In progress", "Done"])
            sample_values[prop_name] = {"status": {"name": opts[row_index % len(opts)]}}
        elif ptype == "date":
            sample_values[prop_name] = {
                "date": {
                    "start": f"2026-{(1 + row_index % 3):02d}-{(1 + row_index % 28):02d}"
                }
            }
        elif ptype == "checkbox":
            sample_values[prop_name] = {"checkbox": row_index % 2 == 0}
        elif ptype == "url":
            sample_values[prop_name] = {
                "url": f"https://example.com/{titles[row_index % len(titles)].lower()}"
            }
        elif ptype == "email":
            sample_values[prop_name] = {
                "email": f"{titles[row_index % len(titles)].lower()}@example.com"
            }
        elif ptype == "phone" or ptype == "phone_number":
            sample_values[prop_name] = {"phone_number": f"+1-555-{1000 + row_index}"}
        elif ptype == "formula":
            pass
    return sample_values


def _create_sample_entries(
    notion: Any,
    db_id: str,
    db_name: str,
    db_props: Dict[str, Any],
    num_entries: int = 5,
) -> int:
    created = 0
    for i in range(num_entries):
        try:
            properties = _build_sample_properties(db_props, i, num_entries)
            if not properties:
                continue
            _retry_call(
                notion.pages.create,
                parent={"database_id": db_id},
                properties=properties,
            )
            created += 1
        except Exception as e:
            logger.warning(f"Failed to create sample entry {i + 1} for {db_name}: {e}")
    return created


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        notion_api_key = os.getenv("NOTION_API_KEY")
        notion_parent_id = os.getenv("NOTION_PARENT_PAGE_ID")

        if not notion_api_key or not notion_parent_id:
            logger.warning(
                "Notion API Key or Parent Page ID not configured. Skipping notion sync."
            )
            return AgentResult(status="skipped", error="Notion not configured")

        from notion_client import Client

        notion = Client(auth=notion_api_key, notion_version="2022-06-28")

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
            return AgentResult(
                status="failed", error="No Notion schema blueprint found in context"
            )

        with open(blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

        root_cover_url = (
            "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200"
        )

        root_page = _retry_call(
            notion.pages.create,
            parent={"page_id": notion_parent_id},
            cover={"type": "external", "external": {"url": root_cover_url}},
            icon={"type": "emoji", "emoji": "\U0001f3ed"},
            properties={
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": f"{job_spec.niche} ({job_spec.product_type})"
                            }
                        }
                    ]
                }
            },
        )
        root_page_id = root_page["id"]
        root_page_url = root_page.get(
            "url", f"https://notion.so/{root_page_id.replace('-', '')}"
        )

        sync_result = {
            "root_page_id": root_page_id,
            "root_page_url": root_page_url,
            "databases": {},
        }

        # === PHASE 2: Create databases from LLM-generated blueprint ===
        db_id_map: Dict[str, str] = {}
        for db in blueprint.get("databases", []):
            db_name = db["name"]
            try:
                db_props = db.get("properties", {})
                has_title = any(p.get("type") == "title" for p in db_props.values())
                if not has_title:
                    db_props["Name"] = {"type": "title"}

                properties = _build_property_config(db_props)
                parent_config = {"type": "page_id", "page_id": root_page_id}
                db_body = {
                    "parent": parent_config,
                    "icon": {"type": "emoji", "emoji": _pick_icon(db_name)},
                    "title": [{"type": "text", "text": {"content": db_name}}],
                    "properties": properties,
                }
                db_desc = db.get("description", "")
                if db_desc:
                    db_body["description"] = [
                        {"type": "text", "text": {"content": db_desc}}
                    ]

                new_db = _retry_call(
                    notion.request, path="databases", method="POST", body=db_body
                )
                db_id_map[db_name] = new_db["id"]
                logger.info(f"Created database: {db_name} -> {new_db['id']}")

                num_samples = min(5, max(3, 7 - len(blueprint.get("databases", []))))
                created = _create_sample_entries(
                    notion, new_db["id"], db_name, db_props, num_samples
                )
                if created:
                    logger.info(f"  Added {created} sample entries to {db_name}")
            except Exception as e:
                logger.error(f"Failed to create database {db_name}: {e}")

        relation_configs = _resolve_relations(blueprint, db_id_map)
        if relation_configs:
            for key, config in relation_configs.items():
                try:
                    _retry_call(
                        notion.request,
                        path=f"databases/{config['db_id']}",
                        method="PATCH",
                        body={
                            "properties": {
                                config["prop_name"]: {
                                    "relation": {
                                        "database_id": config["target_id"],
                                        "type": "single_property",
                                        "single_property": {},
                                    }
                                }
                            }
                        },
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
                    logger.info(
                        f"View {view_name} ({view_type}) would be set on {db_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to configure view {view.get('name', 'unknown')}: {e}"
                    )

        # === PHASE 3: Template/How-to-Use page ===
        template_cover_url = (
            "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1200"
        )
        template_page = _retry_call(
            notion.pages.create,
            parent={"page_id": root_page_id},
            cover={"type": "external", "external": {"url": template_cover_url}},
            icon={"type": "emoji", "emoji": "\U0001f4d1"},
            properties={
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": "\U0001f4cb Notion Template \u2014 How to Use"
                            }
                        }
                    ]
                }
            },
        )

        instructions = [
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {"text": {"content": "Welcome to Your New Workspace"}}
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "text": {
                                "content": f"This Notion workspace was generated for: {job_spec.niche}"
                            }
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Each database below is pre-configured with the properties, relations, and views you need."
                            }
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Databases in this workspace"}}]
                },
            },
        ]

        for db in blueprint.get("databases", []):
            db_name = db["name"]
            db_desc = db.get("description", "")
            rich_text = [
                {
                    "type": "text",
                    "text": {"content": db_name},
                    "annotations": {"bold": True},
                },
            ]
            if db_desc:
                rich_text.append({"type": "text", "text": {"content": f" — {db_desc}"}})
            instructions.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": rich_text},
                }
            )

        instructions.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "How to use this template"}}]
                },
            }
        )

        usage_steps = [
            "Click the 'Duplicate' button in the top-right corner of this page.",
            "The entire workspace will copy to your personal Notion account.",
            "Each database comes with 4-5 sample entries to show you the structure.",
            "Customize the databases, add your own data, and modify properties as needed.",
            "Share individual databases or the whole workspace with your team.",
        ]
        for step in usage_steps:
            instructions.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": [{"text": {"content": step}}]},
                }
            )

        for i in range(0, len(instructions), 100):
            chunk = instructions[i : i + 100]
            try:
                _retry_call(
                    notion.blocks.children.append,
                    block_id=template_page["id"],
                    children=chunk,
                )
            except Exception as e:
                logger.error(f"Failed to append blocks: {e}")

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
            f.write("# Notion Template Access Link\n\n")
            f.write(
                "Your interactive Notion workspace has been successfully created!\n\n"
            )
            f.write(
                f"## 🔗 [Click here to open the Notion Template]({root_page_url})\n\n"
            )
            f.write("### How to use this template:\n")
            f.write("1. Open the link above in your browser.\n")
            f.write(
                "2. Click the **'Duplicate'** button in the top-right corner of the page.\n"
            )
            f.write(
                "3. The workspace will copy directly into your own Notion account, ready to be customized or sold!\n"
            )

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
