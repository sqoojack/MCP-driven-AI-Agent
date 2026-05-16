from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from create_ppt import generate_ppt_from_report, generate_report
from ppt_draw import create_node, generate_diagram_to_ppt


@dataclass
class Step:
    name: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    step: str
    tool: str
    status: str
    observation: str = ""
    seconds: float = 0.0


class JsonMemory:
    def __init__(self, path: str = "agent_memory.json") -> None:
        self.path = Path(path)
        self.data = self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def update(self, **kwargs: Any) -> None:
        self.data.update(kwargs)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_run(self, run: dict[str, Any]) -> None:
        runs = self.data.setdefault("runs", [])
        runs.append(run)
        self.data["runs"] = runs[-20:]
        self.update(**self.data)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"preferences": {}, "runs": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"preferences": {}, "runs": []}


class AutonomousPPTAgent:
    def __init__(self, memory: JsonMemory | None = None, on_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.memory = memory or JsonMemory()
        self.state: dict[str, Any] = {}
        self.trace: list[Trace] = []
        self.on_event = on_event
        self.tools: dict[str, Callable[..., Any]] = {
            "remember_preferences": self._remember_preferences,
            "backup_sources": self._backup_sources,
            "generate_outline": self._generate_outline,
            "self_evaluate": self._self_evaluate,
            "repair_outline": self._repair_outline,
            "render_ppt": self._render_ppt,
            "add_diagrams": self._add_diagrams,
            "publish_artifact": self._publish_artifact,
        }

    def run(
        self,
        topic: str,
        content: str,
        source_file_paths: list[str] | None = None,
        num_pages: int | None = None,
        level: str | None = None,
        language: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        font_size: int = 18,
        enable_diagrams: bool = True,
        upload_to_s3: bool = True,
    ) -> dict[str, Any]:
        prefs = self.memory.get("preferences", {})
        self.state = {
            "topic": topic.strip(),
            "content": content.strip(),
            "source_file_paths": source_file_paths or [],
            "num_pages": num_pages or prefs.get("num_pages", 5),
            "level": level or prefs.get("level", "Intermediate"),
            "language": language or prefs.get("language", "Traditional Chinese"),
            "model_name": model_name or prefs.get("model_name", "gpt-oss:20b"),
            "temperature": temperature if temperature is not None else prefs.get("temperature", 0.7),
            "font_size": font_size,
            "enable_diagrams": enable_diagrams,
            "upload_to_s3": upload_to_s3,
            "warnings": [],
            "outline": {"slides": []},
            "output_path": None,
            "download_url": None,
            "backups": [],
        }
        self._validate_request()

        for step in self._plan():
            self._execute(step)

        result = self._result()
        self.memory.append_run(result)
        return result

    def _plan(self) -> list[Step]:
        steps = [
            Step("Store user preferences", "remember_preferences"),
            Step("Generate initial outline", "generate_outline"),
            Step("Evaluate outline quality", "self_evaluate"),
            Step("Repair outline if needed", "repair_outline"),
            Step("Render PowerPoint", "render_ppt"),
        ]

        if self.state["upload_to_s3"]:
            steps.insert(1, Step("Backup source files", "backup_sources"))
            steps.append(Step("Publish generated deck", "publish_artifact"))

        if self.state["enable_diagrams"]:
            steps.insert(-1 if self.state["upload_to_s3"] else len(steps), Step("Add diagram slides", "add_diagrams"))

        return steps

    def _execute(self, step: Step) -> None:
        started = time.time()
        self._emit("running", step, "Working...")

        try:
            observation = self.tools[step.tool](**step.args)
            self.trace.append(Trace(step.name, step.tool, "ok", str(observation), time.time() - started))
            self._emit("done", step, str(observation))
        except Exception as exc:
            self.trace.append(Trace(step.name, step.tool, "failed", str(exc), time.time() - started))
            self._emit("failed", step, str(exc))

            if step.tool in {"generate_outline", "self_evaluate", "repair_outline", "render_ppt"}:
                raise

            self.state["warnings"].append(f"{step.name} failed: {exc}")


    def _emit(self, status: str, step: Step, message: str) -> None:
        if self.on_event:
            self.on_event(
                {
                    "status": status,
                    "step": step.name,
                    "tool": step.tool,
                    "message": message,
                }
            )

    def _validate_request(self) -> None:
        if not self.state["topic"]:
            raise ValueError("topic is required")
        if not self.state["content"]:
            raise ValueError("content is required")
        if not 1 <= int(self.state["num_pages"]) <= 30:
            raise ValueError("num_pages must be between 1 and 30")
        if not 0 <= float(self.state["temperature"]) <= 1:
            raise ValueError("temperature must be between 0 and 1")

    def _remember_preferences(self) -> str:
        self.memory.update(
            preferences={
                "num_pages": self.state["num_pages"],
                "level": self.state["level"],
                "language": self.state["language"],
                "model_name": self.state["model_name"],
                "temperature": self.state["temperature"],
            }
        )
        return "preferences saved"

    def _backup_sources(self) -> str:
        aws = self._aws()
        if not aws:
            return "aws disabled"

        backups = []
        for path in self.state["source_file_paths"]:
            if not path or not os.path.exists(path):
                self.state["warnings"].append(f"source file not found: {path}")
                continue
            key = f"uploads/{os.path.basename(path)}"
            if aws.upload_file(path, key):
                backups.append(key)
            else:
                self.state["warnings"].append(f"upload failed: {path}")

        self.state["backups"] = backups
        return f"{len(backups)} source files backed up"

    def _generate_outline(self) -> str:
        outline = generate_report(
            all_texts=[self.state["content"]],
            st_status=None,
            num_pages=self.state["num_pages"],
            level=self.state["level"],
            language=self.state["language"],
            model=self.state["model_name"],
            temperature=self.state["temperature"],
        )
        self.state["outline"] = outline
        return f"{len(outline.get('slides', []))} slides generated"

    def _self_evaluate(self) -> str:
        slides = self.state["outline"].get("slides", [])
        issues = []

        if not isinstance(slides, list) or not slides:
            issues.append("outline has no slides")

        if len(slides) != self.state["num_pages"]:
            issues.append(f"expected {self.state['num_pages']} slides, got {len(slides)}")

        for i, slide in enumerate(slides, 1):
            title = str(slide.get("title", "")).strip() if isinstance(slide, dict) else ""
            content = str(slide.get("content", "")).strip() if isinstance(slide, dict) else ""
            if not title:
                issues.append(f"slide {i} has no title")
            if len(content) < 20:
                issues.append(f"slide {i} content is too short")

        self.state["evaluation_issues"] = issues
        return "pass" if not issues else "; ".join(issues)

    def _repair_outline(self) -> str:
        issues = self.state.get("evaluation_issues", [])
        if not issues:
            return "no repair needed"

        slides = self.state["outline"].get("slides", [])
        fixed = []

        for i in range(self.state["num_pages"]):
            slide = slides[i] if i < len(slides) and isinstance(slides[i], dict) else {}
            title = str(slide.get("title") or f"Slide {i + 1}").strip()
            content = str(slide.get("content") or "").strip()
            fixed.append({"title": title, "content": content or self._fallback_content(i)})

        self.state["outline"] = {"slides": fixed}
        self.state["warnings"].append("outline was repaired by self-evaluation")
        return "outline repaired"

    def _render_ppt(self) -> str:
        output_dir = Path("Output")
        output_dir.mkdir(exist_ok=True)

        path = output_dir / f"{self._safe_name(self.state['topic'])}.pptx"
        generate_ppt_from_report(self.state["outline"], str(path), font_size=self.state["font_size"])
        self.state["output_path"] = str(path)
        return str(path)

    def _add_diagrams(self) -> str:
        try:
            nodes = create_node(
                json.dumps(self.state["outline"], ensure_ascii=False),
                language=self.state["language"],
                model=self.state["model_name"],
                temperature=self.state["temperature"],
            )
            if not nodes:
                return "diagram skipped: no nodes"
            generate_diagram_to_ppt(self.state["output_path"], None, nodes)
            return "diagram slides added"
        except Exception as exc:
            self.state["warnings"].append(f"diagram generation failed: {exc}")
            return "diagram skipped"

    def _publish_artifact(self) -> str:
        aws = self._aws()
        path = self.state["output_path"]

        if not aws:
            return "aws disabled"
        if not path or not os.path.exists(path):
            raise ValueError("ppt output not found")

        key = f"generated_ppt/{os.path.basename(path)}"
        if not aws.upload_file(path, key):
            self.state["warnings"].append("ppt upload failed")
            return "publish failed"

        self.state["download_url"] = aws.get_download_url(key)
        return "published"

    def _result(self) -> dict[str, Any]:
        return {
            "status": "success",
            "topic": self.state["topic"],
            "output_path": self.state["output_path"],
            "download_url": self.state["download_url"],
            "slide_count": len(self.state["outline"].get("slides", [])),
            "source_backups": self.state["backups"],
            "warnings": self.state["warnings"],
            "trace": [asdict(t) for t in self.trace],
        }

    def _aws(self) -> Any | None:
        try:
            from aws_utils import AWSManager

            return AWSManager()
        except Exception as exc:
            self.state["warnings"].append(f"aws unavailable: {exc}")
            return None

    def _fallback_content(self, index: int) -> str:
        chunks = re.split(r"[\n。.!?]+", self.state["content"])
        chunks = [c.strip() for c in chunks if c.strip()]
        start = index * 3
        selected = chunks[start : start + 3] or chunks[:3] or [self.state["content"][:200]]
        return "\n".join(f"- {text}" for text in selected)

    @staticmethod
    def _safe_name(text: str) -> str:
        return re.sub(r"[^\w.-]+", "_", text.strip(), flags=re.UNICODE).strip("_") or "generated_ppt"