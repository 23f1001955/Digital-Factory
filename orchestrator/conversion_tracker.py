import os
import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProductConversionData:
    landing_visitors: int = 0
    gumroad_visits_direct: int = 0
    gumroad_sales_landing: int = 0
    gumroad_sales_direct: int = 0


class ConversionTracker:
    def __init__(self, storage_path: str = "outputs/_analytics/conversion_data.json"):
        self.storage_path = storage_path
        self._data: Dict[str, ProductConversionData] = {}
        self._load()

    def record_landing_visit(self, slug: str, utm_params: dict) -> None:
        if slug not in self._data:
            self._data[slug] = ProductConversionData()
        self._data[slug].landing_visitors += 1
        self._save()

    def record_gumroad_visit_direct(self, slug: str) -> None:
        if slug not in self._data:
            self._data[slug] = ProductConversionData()
        self._data[slug].gumroad_visits_direct += 1
        self._save()

    def record_gumroad_sale(self, slug: str, source: str) -> None:
        if slug not in self._data:
            self._data[slug] = ProductConversionData()
        if source == "landing":
            self._data[slug].gumroad_sales_landing += 1
        else:
            self._data[slug].gumroad_sales_direct += 1
        self._save()

    def compute_report(self, min_impressions: int = 100) -> Optional[dict]:
        report = None
        for slug, d in self._data.items():
            total_visitors = d.landing_visitors + d.gumroad_visits_direct
            if total_visitors < min_impressions:
                continue
            landing_cvr = (d.gumroad_sales_landing / d.landing_visitors * 100) if d.landing_visitors > 0 else 0.0
            direct_cvr = (d.gumroad_sales_direct / d.gumroad_visits_direct * 100) if d.gumroad_visits_direct > 0 else 0.0
            winner = "landing_page" if landing_cvr > direct_cvr else ("direct" if direct_cvr > landing_cvr else "tie")
            report = {
                "slug": slug,
                "landing_visitors": d.landing_visitors,
                "gumroad_visits_direct": d.gumroad_visits_direct,
                "gumroad_sales_landing": d.gumroad_sales_landing,
                "gumroad_sales_direct": d.gumroad_sales_direct,
                "landing_cvr": round(landing_cvr, 2),
                "direct_cvr": round(direct_cvr, 2),
                "winner": winner,
            }
        return report

    def save_report(self, path: str = "outputs/_analytics/conversion_report.json") -> None:
        report = self.compute_report(min_impressions=1)
        if report:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(report, f, indent=2)
            logger.info("Conversion report saved to %s", path)

    def _load(self) -> None:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    raw = json.load(f)
                for slug, d in raw.items():
                    self._data[slug] = ProductConversionData(**d)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Failed to load conversion data: %s", e)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        raw = {slug: vars(d) for slug, d in self._data.items()}
        with open(self.storage_path, "w") as f:
            json.dump(raw, f, indent=2)
