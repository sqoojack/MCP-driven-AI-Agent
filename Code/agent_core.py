from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from create_ppt import generate_ppt_from_report, generate_report
from ppt_draw import create_node, generate_diagram_to_ppt


@dataclass
class AgentStep:
    name: str
    status: str = "pending"
    observation: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    def start(self) -> None:
        self.status = "running"
        self.started_at = time.time()

    def complete(self, observation: str = "") -> None:
        self.status = "completed"
        self.observation = observation
        self.finished_at = time.time()

    def fail(self, observation: str) -> None:
        self.status = "failed"
        self.observation = observation
        self.finished_at = time.time()


@dataclass
class AgentRunResult:
    topic: str
    status: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    slide_count: int = 0
    source_backup_keys: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class PPTAgent:
    def __init__(
        self,
        output_dir: str = "Output",
        aws_manager_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.output_dir = output_dir
        self.aws_manager_factory = aws_manager_factory

    def run(
        self,
        topic: str,
        content: str,
        source_file_paths: Optional[List[str]] = None,
        num_pages: int = 5,
        level: str = "Intermediate",
        language: str = "Traditional Chinese",
        model_name: str = "gpt-oss:20b",
        temperature: float = 0.7,
        font_size: int = 18,
        enable_diagrams: bool = True,
        upload_to_s3: bool = True,
    ) -> AgentRunResult:
        source_file_paths = source_file_paths or []
        warnings: List[str] = []
        trace: List[AgentStep] = []
        output_path: Optional[str] = None
        download_url: Optional[str] = None
        source_backup_keys: List[str] = []
        structure: Dict[str, Any] = {"slides": []}

        def step(name: str) -> AgentStep:
            agent_step = AgentStep(name=name)
            agent_step.start()
            trace.append(agent_step)
            return agent_step

        try:
            current_step = step("validate_inputs")
            self._validate_inputs(topic, content, num_pages, temperature, font_size)
            current_step.complete("Inputs are valid.")

            current_step = step("plan_execution")
            plan = self._build_plan(enable_diagrams=enable_diagrams, upload_to_s3=upload_to_s3)
            current_step.complete(" -> ".join(plan))

            if upload_to_s3:
                current_step = step("backup_sources")
                source_backup_keys = self._backup_sources(source_file_paths, warnings)
                current_step.complete(f"Backed up {len(source_backup_keys)} source files.")

            current_step = step("generate_slide_outline")
            structure = generate_report(
                all_texts=[content],
                st_status=None,
                num_pages=num_pages,
                level=level,
                language=language,
                model=model_name,
                temperature=temperature,
            )
            current_step.complete(f"Generated {len(structure.get('slides', []))} slide drafts.")

            current_step = step("validate_slide_outline")
            structure = self._validate_slide_structure(structure, num_pages, warnings)
            current_step.complete(f"Validated {len(structure.get('slides', []))} slides.")

            current_step = step("render_pptx")
            os.makedirs(self.output_dir, exist_ok=True)
            output_path = os.path.join(self.output_dir, f"{self._safe_filename(topic)}.pptx")
            generate_ppt_from_report(structure, output_path, font_size=font_size)
            current_step.complete(output_path)

            if enable_diagrams:
                current_step = step("generate_diagrams")
                try:
                    nodes = create_node(
                        json.dumps(structure, ensure_ascii=False),
                        language=language,
                        model=model_name,
                        temperature=temperature,
                    )
                    if nodes:
                        generate_diagram_to_ppt(output_path, None, nodes)
                        current_step.complete("Diagram slides were appended.")
                    else:
                        warning = "Diagram generation returned no nodes; PPT content slides were still created."
                        warnings.append(warning)
                        current_step.complete(warning)
                except Exception as exc:
                    warning = f"Diagram generation failed but PPT creation continued: {exc}"
                    warnings.append(warning)
                    current_step.complete(warning)

            if upload_to_s3:
                current_step = step("publish_ppt")
                download_url = self._publish(output_path, warnings)
                current_step.complete("Published to S3." if download_url else "S3 publish skipped or failed.")

            return AgentRunResult(
                topic=topic,
                status="success",
                output_path=output_path,
                download_url=download_url,
                slide_count=len(structure.get("slides", [])),
                source_backup_keys=source_backup_keys,
                warnings=warnings,
                trace=[asdict(item) for item in trace],
            )
        except Exception as exc:
            if trace and trace[-1].status == "running":
                trace[-1].fail(str(exc))
            return AgentRunResult(
                topic=topic,
                status="failed",
                output_path=output_path,
                download_url=download_url,
                slide_count=len(structure.get("slides", [])),
                source_backup_keys=source_backup_keys,
                warnings=warnings + [str(exc)],
                trace=[asdict(item) for item in trace],
            )

    def _build_plan(self, enable_diagrams: bool, upload_to_s3: bool) -> List[str]:
        plan = ["validate inputs", "generate slide outline", "validate outline", "render PPTX"]
        if enable_diagrams:
            plan.append("append diagram slides")
        if upload_to_s3:
            plan.append("backup sources and publish artifact")
        return plan

    def _validate_inputs(
        self,
        topic: str,
        content: str,
        num_pages: int,
        temperature: float,
        font_size: int,
    ) -> None:
        if not topic or not topic.strip():
            raise ValueError("topic is required")
        if not content or not content.strip():
            raise ValueError("content is required")
        if not 1 <= num_pages <= 30:
            raise ValueError("num_pages must be between 1 and 30")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        if not 8 <= font_size <= 44:
            raise ValueError("font_size must be between 8 and 44")

    def _validate_slide_structure(
        self,
        structure: Dict[str, Any],
        requested_pages: int,
        warnings: List[str],
    ) -> Dict[str, Any]:
        if not isinstance(structure, dict):
            raise ValueError("LLM output must be a JSON object")

        slides = structure.get("slides")
        if not isinstance(slides, list) or not slides:
            raise ValueError("LLM output must contain a non-empty slides list")

        normalized_slides = []
        for index, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                warnings.append(f"Slide {index} was not an object and was skipped.")
                continue
            title = str(slide.get("title") or f"Slide {index}").strip()
            content = str(slide.get("content") or "").strip()
            if not content:
                warnings.append(f"Slide {index} had empty content.")
            normalized_slides.append({"title": title, "content": content})

        if not normalized_slides:
            raise ValueError("No valid slides were generated")

        if len(normalized_slides) != requested_pages:
            warnings.append(
                f"Requested {requested_pages} slides, but the model returned {len(normalized_slides)} valid slides."
            )

        return {"slides": normalized_slides[:requested_pages]}

    def _backup_sources(self, source_file_paths: List[str], warnings: List[str]) -> List[str]:
        if not source_file_paths:
            return []

        aws_manager = self._get_aws_manager(warnings)
        if not aws_manager:
            return []

        uploaded_keys: List[str] = []
        for file_path in source_file_paths:
            if not file_path or not os.path.exists(file_path):
                warnings.append(f"Source file not found and was skipped: {file_path}")
                continue
            file_name = os.path.basename(file_path)
            object_key = f"uploads/{file_name}"
            if aws_manager.upload_file(file_path, object_key):
                uploaded_keys.append(object_key)
            else:
                warnings.append(f"Failed to upload source file: {file_path}")
        return uploaded_keys

    def _publish(self, output_path: Optional[str], warnings: List[str]) -> Optional[str]:
        if not output_path or not os.path.exists(output_path):
            raise ValueError("PPT output path does not exist")

        aws_manager = self._get_aws_manager(warnings)
        if not aws_manager:
            return None

        object_key = f"generated_ppt/{os.path.basename(output_path)}"
        if not aws_manager.upload_file(output_path, object_key):
            warnings.append("Failed to upload generated PPT to S3.")
            return None
        return aws_manager.get_download_url(object_key)

    def _get_aws_manager(self, warnings: List[str]) -> Optional[Any]:
        if self.aws_manager_factory is None:
            try:
                from aws_utils import AWSManager

                self.aws_manager_factory = AWSManager
            except Exception as exc:
                warnings.append(f"AWS manager is unavailable: {exc}")
                return None

        try:
            return self.aws_manager_factory()
        except Exception as exc:
            warnings.append(f"AWS initialization failed: {exc}")
            return None

    def _safe_filename(self, topic: str) -> str:
        normalized = re.sub(r"[^\w\-.]+", "_", topic.strip(), flags=re.UNICODE).strip("_")
        return normalized or "generated_presentation"
