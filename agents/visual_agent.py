import os
import json
import logging
from openai import OpenAI
import requests

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        if "image_prompts" not in context:
            raise ValueError("image_prompts dependency not met")
            
        with open(context["image_prompts"], "r") as f:
            prompts = json.load(f)
            
        output_dir = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(output_dir, exist_ok=True)
        
        api_key = os.getenv("OPENAI_API_KEY")
        
        # If no key, generate placeholders
        if not api_key or api_key == "your_openai_api_key_here":
            logger.warning("OPENAI_API_KEY missing or placeholder. Generating local placeholder images.")
            
            for i, p in enumerate(prompts):
                path = os.path.join(output_dir, f"image_{i+1}.png")
                # Create a simple colored square placeholder
                # We'll just write an empty file that Playwright can at least reference,
                # though it won't render an image. Better yet, create a basic SVG or download a dummy image.
                # Here we'll download a dummy placeholder image from placehold.co
                res = requests.get(f"https://placehold.co/800x800/png?text=Image+{i+1}")
                with open(path, "wb") as img_f:
                    img_f.write(res.content)
            
            return AgentResult(status="done", output_path=output_dir, error=None)
            
        client = OpenAI(api_key=api_key)
        
        for i, prompt_text in enumerate(prompts):
            path = os.path.join(output_dir, f"image_{i+1}.png")
            
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt_text,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            
            img_data = requests.get(image_url).content
            with open(path, "wb") as img_f:
                img_f.write(img_data)
                
        return AgentResult(status="done", output_path=output_dir, error=None)
        
    except Exception as e:
        logger.error(f"Visual agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
