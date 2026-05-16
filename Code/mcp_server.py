import contextlib
import json
import sys
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Autonomous_PPT_Agent")


@mcp.tool()
def agent_health_check() -> str:
    return json.dumps(
        {
            "status": "ok",
            "agent": "Autonomous_PPT_Agent",
            "capabilities": [
                "planning",
                "memory",
                "tool orchestration",
                "self-evaluation",
                "ppt generation",
                "diagram generation",
                "s3 publishing",
            ],
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


@mcp.tool()
def create_ppt_from_text(
    topic: str,
    content: str,
    source_file_paths: Optional[list[str]] = None,
    num_pages: int = 5,
    level: str = "Intermediate",
    language: str = "Traditional Chinese",
    model_name: str = "gpt-oss:20b",
    temperature: float = 0.7,
) -> str:
    return run_autonomous_ppt_agent(
        topic=topic,
        content=content,
        source_file_paths=source_file_paths or [],
        num_pages=num_pages,
        level=level,
        language=language,
        model_name=model_name,
        temperature=temperature,
        enable_diagrams=True,
        upload_to_s3=True,
    )


if __name__ == "__main__":
    mcp.run()