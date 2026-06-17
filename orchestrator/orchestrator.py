import os
import json
import logging
import traceback
from typing import List

from .models import JobSpec, ProductSchema, ComponentSpec, AgentResult, PipelinePlan
from .state import load_job_state, save_job_state
from agents.registry import AGENT_REGISTRY
from renderers.base import get_renderer
from agents.evaluation_agent import evaluate, EVALUATION_TARGETS
from orchestrator.notify import dispatch_alert
from agents.review_agent import write_review_log

FILE_AGENT_SUBSTITUTIONS = {
    "content_agent": "notion_content_agent",
    "csv_export_agent": "notion_content_agent",
    "render_agent": "notion_content_agent",
    "diagram_agent": "notion_content_agent",
}

logger = logging.getLogger(__name__)

MAX_QUALITY_RETRIES = 2


class Orchestrator:
    def __init__(self, job_spec_path: str):
        self.job_spec_path = job_spec_path

        with open(job_spec_path, "r") as f:
            self.job_spec = JobSpec(**json.load(f))

        schema_path = os.path.join("schemas", f"{self.job_spec.product_type}.json")
        with open(schema_path, "r") as f:
            self.schema = ProductSchema(**json.load(f))

        self.state_path = os.path.join("outputs", self.job_spec.slug, "job_state.json")
        self.state = load_job_state(self.state_path, self.job_spec.slug)

        self.renderer = None

    def _get_execution_order(self) -> List[ComponentSpec]:
        """Topological sort of components."""
        graph = {c.id: set(c.depends_on) for c in self.schema.components}
        ordered = []
        visited = set()

        def visit(node_id):
            if node_id in visited:
                return
            for dep in graph.get(node_id, []):
                visit(dep)
            visited.add(node_id)
            # Find the component
            for c in self.schema.components:
                if c.id == node_id:
                    ordered.append(c)
                    break

        for c in self.schema.components:
            visit(c.id)

        return ordered

    def _merge_pipeline_plan(self, research_path: str) -> None:
        """Load market_research.json, extract pipeline_plan, merge into schema."""
        if not os.path.exists(research_path):
            logger.warning("No market_research.json found — core components only")
            return

        try:
            with open(research_path, "r") as f:
                research = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse market_research.json: {e}")
            return

        raw_plan = research.get("pipeline_plan")
        if not raw_plan or "components" not in raw_plan:
            logger.info("No pipeline_plan in research — core components only")
            return

        try:
            plan = PipelinePlan(**raw_plan)
        except Exception as e:
            logger.warning(f"Failed to validate pipeline_plan: {e}")
            return

        RESERVED_IDS = {
            "market_research",
            "images",
            "package",
            "notion_schema",
            "notion_tree",
            "gumroad_research",
            "gumroad_publish",
            "landing_page",
            "social_promotion",
        }

        existing_ids = {c.id for c in self.schema.components}
        allowed_agents = set(AGENT_REGISTRY.keys())

        added = 0
        accepted_ids = set(existing_ids)
        for comp in plan.components:
            if comp.id in RESERVED_IDS:
                logger.warning(f"Skipping reserved ID '{comp.id}'")
                continue
            if comp.id in accepted_ids:
                logger.warning(f"Skipping duplicate '{comp.id}'")
                continue
            if comp.agent not in allowed_agents:
                logger.warning(f"Skipping unknown agent '{comp.agent}' for '{comp.id}'")
                continue

            if not all(dep in accepted_ids for dep in comp.depends_on):
                logger.warning(f"Skipping '{comp.id}' — invalid dependencies")
                continue

            spec = ComponentSpec(
                id=comp.id,
                agent=comp.agent,
                output=comp.output,
                depends_on=comp.depends_on,
                template=comp.template,
                format=comp.format,
                delivery=comp.delivery,
                capabilities=comp.capabilities,
            )
            self.schema.components.append(spec)
            accepted_ids.add(comp.id)
            added += 1
            logger.info(f"Added dynamic component: {comp.id} ({comp.agent})")

        # Ensure package runs last — depends on all non-wizard-gated components
        for c in self.schema.components:
            if c.id == "package":
                c.depends_on = [
                    comp.id
                    for comp in self.schema.components
                    if comp.id != "package"
                    and comp.id
                    not in (
                        "gumroad_research",
                        "gumroad_publish",
                        "landing_page",
                        "social_promotion",
                    )
                ]
                break

        logger.info(f"Pipeline plan merged: {added} dynamic components")

    def _merge_format_recommendations(self, research_path: str) -> None:
        """Merge market_agent's recommended_formats into component active_formats."""
        try:
            with open(research_path) as f:
                research = json.load(f)
            fmt_recs = research.get("recommended_formats", {})
            if not fmt_recs:
                return  # legacy mode

            comp_map = {c.id: c for c in self.schema.components}
            for comp_id, formats in fmt_recs.items():
                comp = comp_map.get(comp_id)
                if not comp:
                    logger.warning(
                        "recommended_formats references unknown component: %s", comp_id
                    )
                    continue
                if not comp.capabilities:
                    logger.warning(
                        "recommended_formats for %s but component has no capabilities",
                        comp_id,
                    )
                    continue
                active = [f for f in formats if f in comp.capabilities]
                if active:
                    comp.active_formats = active
                    logger.info(
                        "Component %s active formats: %s", comp_id, active
                    )
        except Exception as e:
            logger.error("Failed to merge format recommendations: %s", e)

    def _switch_schema(self, recommended_product_type: str) -> None:
        """Replace current schema with one matching recommended product type."""
        schema_path = os.path.join("schemas", f"{recommended_product_type}.json")
        if not os.path.exists(schema_path):
            logger.warning(
                f"Schema {recommended_product_type}.json not found \u2014 falling back to research_pack"
            )
            schema_path = os.path.join("schemas", "research_pack.json")
        with open(schema_path) as f:
            self.schema = ProductSchema(**json.load(f))
        self.job_spec.product_type = recommended_product_type
        logger.info(f"Schema switched to: {recommended_product_type}")

    def _build_delivery_map(self) -> dict:
        """Build delivery map from all schema components with resolved output paths."""
        delivery_map = {}
        for comp in self.schema.components:
            state = self.state.components.get(comp.id)
            entry = {"delivery": list(comp.delivery)}

            if state and state.output_paths:
                entry["outputs"] = dict(state.output_paths)
            elif state and state.output_path:
                entry["outputs"] = {comp.id: state.output_path}
            else:
                resolved = comp.output.replace("{slug}", self.job_spec.slug)
                default_path = os.path.join(os.getcwd(), "outputs", self.job_spec.slug, resolved)
                entry["outputs"] = {comp.id: default_path}

            delivery_map[comp.id] = entry
        return delivery_map

    def run(self):
        logger.info("Starting pipeline for slug: %s", self.job_spec.slug)
        ordered_components = self._get_execution_order()

        # Check if we need a renderer
        needs_renderer = any(c.uses_renderer for c in ordered_components)
        if needs_renderer and not self.renderer:
            self.renderer = get_renderer()

        total = len(ordered_components)
        done_count = 0

        logger.info("Pipeline: %s components", total)

        idx = 0
        while idx < len(ordered_components):
            component = ordered_components[idx]
            idx += 1
            state_result = self.state.components.get(component.id)
            if state_result and state_result.status == "done":
                done_count += 1
                logger.info("%s/%s %s (already done)", done_count, total, component.id)
                continue

            # Check dependencies
            deps_ok = True
            context = {}
            for dep in component.depends_on:
                dep_state = self.state.components.get(dep)
                if not dep_state:
                    deps_ok = False
                    logger.warning(
                        "Component %s blocked by dependency %s (not found)",
                        component.id,
                        dep,
                    )
                    break
                if dep_state.status == "done":
                    context[dep] = dep_state.output_path
                elif dep_state.status == "skipped":
                    context[dep] = None
                    logger.info(
                        "Component %s dependency %s was skipped — continuing",
                        component.id,
                        dep,
                    )
                else:
                    deps_ok = False
                    logger.warning(
                        "Component %s blocked by dependency %s (status: %s)",
                        component.id,
                        dep,
                        dep_state.status,
                    )
                    break

            if not deps_ok:
                self.state.components[component.id] = AgentResult(
                    status="skipped", error="dependency not met"
                )
                save_job_state(self.state, self.state_path)
                continue

            # Inject renderer if needed
            if component.uses_renderer:
                context["renderer"] = self.renderer

            agent_func = AGENT_REGISTRY.get(component.agent)

            # Skip landing_page if not enabled
            if (
                component.id == "landing_page"
                and not self.job_spec.landing_page_enabled
            ):
                self.state.components[component.id] = AgentResult(
                    status="skipped", error="landing page not enabled"
                )
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            # Skip social_promotion if not enabled
            if (
                component.id == "social_promotion"
                and not self.job_spec.social_promotion_enabled
            ):
                self.state.components[component.id] = AgentResult(
                    status="skipped", error="social promotion not enabled"
                )
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            # Skip gumroad if not enabled
            if (
                component.id in ("gumroad_research", "gumroad_publish")
                and not self.job_spec.gumroad_enabled
            ):
                self.state.components[component.id] = AgentResult(
                    status="skipped", error="gumroad not enabled"
                )
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            # Skip notion_schema/notion_tree if notion_sync not enabled
            if (
                component.id in ("notion_schema", "notion_tree")
                and not self.job_spec.notion_sync
            ):
                self.state.components[component.id] = AgentResult(
                    status="skipped", error="notion sync not enabled"
                )
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

# notion_only mode: skip package, substitute file agents
            if self.job_spec.notion_only:
                if component.id == "package":
                    self.state.components[component.id] = AgentResult(
                        status="skipped", error="notion_only mode: no ZIP"
                    )
                    save_job_state(self.state, self.state_path)
                    done_count += 1
                    logger.warning(
                        "%s/%s %s (notion_only — skipped)",
                        done_count,
                        total,
                        component.id,
                    )
                    continue
                substituted = FILE_AGENT_SUBSTITUTIONS.get(component.agent)
                if substituted:
                    agent_func = AGENT_REGISTRY.get(substituted)
                    logger.info(
                        "%s/%s %s (%s → %s)",
                        done_count,
                        total,
                        component.id,
                        component.agent,
                        substituted,
                    )

            if not agent_func:
                logger.error("Agent %s not found in registry", component.agent)
                self.state.components[component.id] = AgentResult(
                    status="failed", error=f"Agent {component.agent} not in registry"
                )
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.error(
                    "%s/%s %s - agent not found", done_count, total, component.id
                )
                continue

            self.state.components[component.id] = AgentResult(status="running")
            save_job_state(self.state, self.state_path)

            done_count += 1
            logger.info("%s/%s %s...", done_count, total, component.id)

            # Inject delivery_map for agents that need routing info
            if component.agent in ("packaging_agent", "gumroad_agent"):
                context["_delivery_map"] = self._build_delivery_map()

            try:
                result = agent_func(component, self.job_spec, context)
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(
                    "Agent %s (%s) raised unhandled exception:\n%s",
                    component.agent,
                    component.id,
                    tb,
                )
                result = AgentResult(status="failed", error=f"Unhandled exception: {e}")


            self.state.components[component.id] = result
            save_job_state(self.state, self.state_path)

            # Phase 2: Quality validation gate
            if result.status == "done" and component.agent in EVALUATION_TARGETS:
                output_path = result.output_path
                if output_path and os.path.exists(output_path):
                    for retry_num in range(MAX_QUALITY_RETRIES + 1):
                        report = evaluate(component, self.job_spec, context, output_path)
                        if report.passed:
                            logger.info(
                                "Quality check PASSED for %s (score=%.2f)",
                                component.id, report.score,
                            )
                            break

                        if retry_num < MAX_QUALITY_RETRIES:
                            logger.warning(
                                "Quality check FAILED for %s (score=%.2f, attempt %d/%d) — retrying",
                                component.id, report.score, retry_num + 1, MAX_QUALITY_RETRIES,
                            )
                            context["_quality_feedback"] = report.fix_prompt
                            try:
                                result = agent_func(component, self.job_spec, context)
                                if result.status == "done":
                                    output_path = result.output_path
                                    self.state.components[component.id] = result
                                    save_job_state(self.state, self.state_path)
                                else:
                                    logger.error("Retry agent failed for %s", component.id)
                                    break
                            except Exception as e:
                                logger.error("Retry exception for %s: %s", component.id, e)
                                break
                        else:
                            logger.error(
                                "Quality check FAILED for %s after %d retries — marking as failed",
                                component.id, MAX_QUALITY_RETRIES,
                            )
                            result = AgentResult(
                                status="failed",
                                error=f"Quality check failed after {MAX_QUALITY_RETRIES} retries (score={report.score})",
                            )
                            self.state.components[component.id] = result
                            save_job_state(self.state, self.state_path)

                    dispatch_alert(report, self.job_spec, component.id)
                    if report.needs_human_review:
                        write_review_log(component, self.job_spec, report)
                        logger.info("Review log created for %s — flagged for human review", component.id)

            # After market_agent completes, check for schema switch + merge pipeline_plan
            if component.id == "market_research" and result.status == "done":
                # Check if we're in discovery mode and need to switch schema
                if self.job_spec.product_type == "discovery":
                    try:
                        with open(result.output_path) as f:
                            research = json.load(f)
                        recommended = research.get("recommended_product_type")
                        confidence = research.get("recommendation_confidence", 0)
                        if recommended and confidence >= 0.5:
                            self._switch_schema(recommended)
                        elif recommended:
                            logger.warning(
                                "Low confidence (%.2f) for '%s' \u2014 falling back to research_pack",
                                confidence, recommended,
                            )
                            self._switch_schema("research_pack")
                        else:
                            logger.warning("No product type recommendation \u2014 falling back to research_pack")
                            self._switch_schema("research_pack")
                    except Exception as e:
                        logger.error("Failed to read market_research.json for schema switch: %s", e)
                        self._switch_schema("research_pack")

                self._merge_pipeline_plan(result.output_path)
                self._merge_format_recommendations(result.output_path)
                ordered_components = self._get_execution_order()
                idx = 0
                total = len(ordered_components)
                logger.info("Pipeline re-planned: %s total components", total)

            if result.status == "done":
                logger.info("%s/%s %s", done_count, total, component.id)
            elif result.status == "failed":
                logger.error(
                    "%s/%s %s - %s", done_count, total, component.id, result.error
                )
            else:
                logger.warning("%s/%s %s", done_count, total, component.id)

        logger.info("Pipeline complete")
        logger.info("Orchestrator run complete. Generating summary report...")
        self._generate_run_summary()

    def _generate_run_summary(self):
        summary_path = os.path.join("outputs", self.job_spec.slug, "run_summary.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"# Run Summary for {self.job_spec.slug}\n\n")
            f.write(f"**Niche:** {self.job_spec.niche}  \n")
            f.write(f"**Product Type:** {self.job_spec.product_type}  \n")
            f.write(f"**Theme:** {getattr(self.job_spec, 'theme', 'default')}  \n\n")
            f.write("## Component Status\n\n")

            for comp_id, result in self.state.components.items():
                icon = (
                    "✅"
                    if result.status == "done"
                    else "❌" if result.status == "failed" else "⏭️"
                )
                f.write(f"- {icon} **{comp_id}**: {result.status}\n")
                if result.error:
                    f.write(f"  - *Error: {result.error}*\n")
                if result.output_path:
                    f.write(f"  - *Output: `{result.output_path}`*\n")

        logger.info("Run summary generated at %s", summary_path)
