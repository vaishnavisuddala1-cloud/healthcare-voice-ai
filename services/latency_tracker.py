import logging
import time
from typing import Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class LatencyTracker:
    """Track and log latency for each pipeline stage."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stages: Dict[str, Dict] = {}
        self.start_time = time.time()

    def start_stage(self, stage_name: str):
        """Mark the start of a pipeline stage."""
        self.stages[stage_name] = {
            "start": time.time(),
            "end": None,
            "duration": None,
        }

    def end_stage(self, stage_name: str):
        """Mark the end of a pipeline stage."""
        if stage_name in self.stages:
            self.stages[stage_name]["end"] = time.time()
            self.stages[stage_name]["duration"] = (
                self.stages[stage_name]["end"] - self.stages[stage_name]["start"]
            ) * 1000  # Convert to milliseconds
            logger.info(
                f"[{self.session_id}] {stage_name}: {self.stages[stage_name]['duration']:.2f}ms"
            )

    def get_stage_latency(self, stage_name: str) -> Optional[float]:
        """Get latency for a specific stage in milliseconds."""
        if stage_name in self.stages:
            return self.stages[stage_name].get("duration")
        return None

    def get_total_latency(self) -> float:
        """Get total pipeline latency in milliseconds."""
        return (time.time() - self.start_time) * 1000

    def get_report(self) -> Dict:
        """Get complete latency report."""
        total_latency = self.get_total_latency()
        
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "stages": {},
            "total_latency_ms": total_latency,
            "stages_summary": {},
        }

        # Add individual stages
        for stage_name, data in self.stages.items():
            if data["duration"] is not None:
                report["stages"][stage_name] = {
                    "duration_ms": data["duration"],
                    "percentage": (data["duration"] / total_latency * 100)
                    if total_latency > 0
                    else 0,
                }

        # Add summary
        report["stages_summary"] = {
            "count": len([s for s in self.stages.values() if s["duration"] is not None]),
            "average_stage_latency_ms": (
                sum([s["duration"] for s in self.stages.values() if s["duration"]])
                / len([s for s in self.stages.values() if s["duration"]])
                if self.stages
                else 0
            ),
        }

        return report

    def log_report(self, max_total_latency: int = 450):
        """Log the complete report and check against threshold."""
        report = self.get_report()
        total_ms = report["total_latency_ms"]

        logger.info(f"=== LATENCY REPORT [{self.session_id}] ===")
        logger.info(json.dumps(report, indent=2))

        # Check threshold
        if total_ms > max_total_latency:
            logger.warning(
                f"⚠️  Total latency {total_ms:.2f}ms EXCEEDS target {max_total_latency}ms"
            )
        else:
            logger.info(
                f"✓ Total latency {total_ms:.2f}ms within target {max_total_latency}ms"
            )

        return report
