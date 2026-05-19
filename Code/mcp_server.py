import contextlib
import json
import sys
from typing import Optional
import os
from pathlib import Path
from urllib.request import urlopen
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Autonomous_PPT_Agent")

def _error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _check_agent() -> dict:
    try:
        from autonomous_ppt_agent import AutonomousPPTAgent

        agent = AutonomousPPTAgent()
        return {"ok": True, "internal_tools": sorted(agent.tools)}
    except Exception as exc:
        return {"ok": False, "error": _error(exc)}


def _check_ollama(timeout: float = 1.5) -> dict:
    try:
        from config import ollama_url

        with urlopen(f"{ollama_url.rstrip('/')}/api/tags", timeout=timeout) as response:
            return {"ok": response.status == 200, "url": ollama_url}
    except Exception as exc:
        return {"ok": False, "error": _error(exc)}


def _check_output_dir(path: str = "Output") -> dict:
    try:
        output_dir = Path(path)
        output_dir.mkdir(exist_ok=True)

        probe = output_dir / ".health_check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

        return {"ok": True, "path": str(output_dir)}
    except Exception as exc:
        return {"ok": False, "path": path, "error": _error(exc)}


def _check_s3() -> dict:
    required_envs = ("AWS_BUCKET_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    missing = [key for key in required_envs if not os.getenv(key)]

    try:
        from aws_utils import AWSManager

        AWSManager()
        return {
            "ok": not missing,
            "env_ok": not missing,
            "region": os.getenv("AWS_REGION", "ap-northeast-1"),
            "missing_envs": missing,
        }
    except Exception as exc:
        return {"ok": False, "env_ok": not missing, "missing_envs": missing, "error": _error(exc)}


@mcp.tool()
def agent_health_check() -> str:
    checks = {
        "agent": _check_agent(),
        "ollama": _check_ollama(),
        "output_dir": _check_output_dir(),
        "s3": _check_s3(),
    }

    ppt_ready = checks["agent"]["ok"] and checks["ollama"]["ok"] and checks["output_dir"]["ok"]
    s3_ready = checks["s3"]["ok"]

    status = "ok" if ppt_ready and s3_ready else "degraded" if ppt_ready else "error"

    return json.dumps(
        {
            "status": status,
            "agent": "Autonomous_PPT_Agent",
            "ready": {
                "ppt_generation": ppt_ready,
                "s3_publishing": s3_ready,
            },
            "checks": checks,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def run_autonomous_ppt_agent(
    topic: str,
    content: str,
    source_file_paths: Optional[list[str]] = None,
    num_pages: Optional[int] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    font_size: int = 18,
    enable_diagrams: bool = True,
    upload_to_s3: bool = True,
) -> str:
    with contextlib.redirect_stdout(sys.stderr):
        from autonomous_ppt_agent import AutonomousPPTAgent

        agent = AutonomousPPTAgent()
        result = agent.run(
            topic=topic,
            content=content,
            source_file_paths=source_file_paths or [],
            num_pages=num_pages,
            level=level,
            language=language,
            model_name=model_name,
            temperature=temperature,
            font_size=font_size,
            enable_diagrams=enable_diagrams,
            upload_to_s3=upload_to_s3,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


# @mcp.tool()
# def create_ppt_from_text(
#     topic: str,
#     content: str,
#     source_file_paths: Optional[list[str]] = None,
#     num_pages: int = 5,
#     level: str = "Intermediate",
#     language: str = "Traditional Chinese",
#     model_name: str = "gpt-oss:20b",
#     temperature: float = 0.7,
# ) -> str:
#     return run_autonomous_ppt_agent(
#         topic=topic,
#         content=content,
#         source_file_paths=source_file_paths or [],
#         num_pages=num_pages,
#         level=level,
#         language=language,
#         model_name=model_name,
#         temperature=temperature,
#         enable_diagrams=True,
#         upload_to_s3=True,
#     )


if __name__ == "__main__":
    mcp.run()