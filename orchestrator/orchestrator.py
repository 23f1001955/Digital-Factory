import os
import json
import logging
from typing import Dict, List

from .models import JobSpec, JobState, ProductSchema, ComponentSpec, AgentResult
from .state import load_job_state, save_job_state
from agents.registry import AGENT_REGISTRY
from renderers.base import get_renderer

logger = logging.getLogger(__name__)

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

        for component in ordered_components:
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
                if not dep_state or dep_state.status != "done":
                    deps_ok = False
                    logger.warning("Component %s blocked by dependency %s", component.id, dep)
                    break
                context[dep] = dep_state.output_path
                
            if not deps_ok:
                self.state.components[component.id] = AgentResult(status="skipped", error=f"dependency not met")
                save_job_state(self.state, self.state_path)
                continue
                
            # Inject renderer if needed
            if component.uses_renderer:
                context["renderer"] = self.renderer
                
            agent_func = AGENT_REGISTRY.get(component.agent)

            # Skip landing_page if not enabled
            if component.id == "landing_page" and not self.job_spec.landing_page_enabled:
                self.state.components[component.id] = AgentResult(status="skipped", error="landing page not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            # Skip social_promotion if not enabled
            if component.id == "social_promotion" and not self.job_spec.social_promotion_enabled:
                self.state.components[component.id] = AgentResult(status="skipped", error="social promotion not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            # Skip gumroad if not enabled
            if component.id in ("gumroad_research", "gumroad_publish") and not self.job_spec.gumroad_enabled:
                self.state.components[component.id] = AgentResult(status="skipped", error="gumroad not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue

            if not agent_func:
                logger.error("Agent %s not found in registry", component.agent)
                self.state.components[component.id] = AgentResult(status="failed", error=f"Agent {component.agent} not in registry")
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.error("%s/%s %s - agent not found", done_count, total, component.id)
                continue
                
            self.state.components[component.id] = AgentResult(status="running")
            save_job_state(self.state, self.state_path)

            done_count += 1
            logger.info("%s/%s %s...", done_count, total, component.id)
            try:
                result = agent_func(component, self.job_spec, context)
            except Exception as e:
                logger.error("Agent %s (%s) raised unhandled exception: %s", component.agent, component.id, e)
                result = AgentResult(status="failed", error=f"Unhandled exception: {e}")
            
            self.state.components[component.id] = result
            save_job_state(self.state, self.state_path)
            
            if result.status == "done":
                logger.info("%s/%s %s", done_count, total, component.id)
            elif result.status == "failed":
                logger.error("%s/%s %s - %s", done_count, total, component.id, result.error)
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
                icon = "✅" if result.status == "done" else "❌" if result.status == "failed" else "⏭️"
                f.write(f"- {icon} **{comp_id}**: {result.status}\n")
                if result.error:
                    f.write(f"  - *Error: {result.error}*\n")
                if result.output_path:
                    f.write(f"  - *Output: `{result.output_path}`*\n")
                    
        logger.info("Run summary generated at %s", summary_path)
