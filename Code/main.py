# python -m streamlit run Code/main.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit as st

from autonomous_ppt_agent import AutonomousPPTAgent, JsonMemory
from uploaded_file import process_uploaded_files


TEMP_DIR = Path("temp_uploads")

TEXT_MODELS = [
    "deepseek-r1:8b",
    "qwen3:14b",
    "qwen2.5:7b",
    "gemma3:27b",
    "deepseek-r1:32b",
    "llava:7b",
    "llava-llama3:8b",
    "llama4:16x17b",
    "gpt-oss:20b",
]

IMAGE_MODELS = [
    "qwen3-vl:8b",
    "gemma3:27b",
    "llava:7b",
    "llava-llama3:8b",
    "llama4:16x17b",
]


def main() -> None:
    st.set_page_config(page_title="MCP-driven-AI-Agent", page_icon="🤖", layout="centered")

    st.title("MCP-driven-AI-Agent")

    memory = JsonMemory()

    uploaded_files = st.file_uploader(
        "Upload files",
        type=["py", "txt", "pdf", "jpg", "jpeg", "png", "docx", "doc", "pptx", "ppt", "mp3", "mp4"],
        accept_multiple_files=True,
    )

    settings = render_settings(memory)

    if st.button("Run Agent", type="primary", use_container_width=True):
        run_agent(uploaded_files, settings, memory)

    if result := st.session_state.get("agent_result"):
        render_result(result)


def render_settings(memory: JsonMemory) -> dict[str, Any]:
    prefs = memory.get("preferences", {})

    with st.expander("Task settings", expanded=True):
        topic = st.text_input("Topic", value="MCP-driven AI Agent")

        col1, col2 = st.columns(2)

        with col1:
            text_model = st.selectbox(
                "Text model",
                TEXT_MODELS,
                index=model_index(TEXT_MODELS, prefs.get("model_name", "deepseek-r1:8b")),
            )
            image_model = st.selectbox("Image model", IMAGE_MODELS, index=0)
            language = st.selectbox(
                "Language",
                ["Traditional Chinese", "English", "Japanese", "Korean"],
                index=0,
            )

        with col2:
            num_pages = st.slider("Slides", 1, 20, int(prefs.get("num_pages", 5)))
            level = st.selectbox(
                "Audience level",
                ["Beginner", "Novice", "Intermediate", "Advanced", "Expert"],
                index=2,
            )
            temperature = st.slider("Temperature", 0.0, 1.0, float(prefs.get("temperature", 0.7)), 0.01)

        enable_diagrams = st.toggle("Generate diagrams", value=True)
        upload_to_s3 = st.toggle("Upload to AWS S3", value=True)

    return {
        "topic": topic,
        "text_model": text_model,
        "image_model": image_model,
        "language": language,
        "num_pages": num_pages,
        "level": level,
        "temperature": temperature,
        "font_size": 18,
        "enable_diagrams": enable_diagrams,
        "upload_to_s3": upload_to_s3,
    }


def run_agent(uploaded_files: list[Any] | None, settings: dict[str, Any], memory: JsonMemory) -> None:
    if not uploaded_files:
        st.warning("Please upload at least one file.")
        return

    flow = build_flow(settings)
    current = {"step": None, "message": ""}
    completed: set[str] = set()

    status_box = st.empty()
    flow_box = st.empty()
    progress = st.progress(0)

    def on_event(event: dict[str, Any]) -> None:
        current["step"] = event["step"]
        current["message"] = event["message"]

        if event["status"] == "done":
            completed.add(event["step"])

        render_flow(status_box, flow_box, progress, flow, current, completed)

    try:
        render_flow(status_box, flow_box, progress, flow, current, completed)

        with st.spinner("Observing uploaded files..."):
            paths = save_uploads(uploaded_files)
            reset_files(uploaded_files)
            content = extract_content(uploaded_files, settings["image_model"])

        agent = AutonomousPPTAgent(memory=memory, on_event=on_event)

        result = agent.run(
            topic=settings["topic"],
            content=content,
            source_file_paths=paths,
            num_pages=settings["num_pages"],
            level=settings["level"],
            language=settings["language"],
            model_name=settings["text_model"],
            temperature=settings["temperature"],
            font_size=settings["font_size"],
            enable_diagrams=settings["enable_diagrams"],
            upload_to_s3=settings["upload_to_s3"],
        )

        completed.update(flow)
        current["step"] = "Completed"
        current["message"] = "The agent finished the task."
        render_flow(status_box, flow_box, progress, flow, current, completed)

        st.session_state["agent_result"] = result
        st.success("Agent completed.")

    except Exception as exc:
        st.error(f"Agent failed: {exc}")


def build_flow(settings: dict[str, Any]) -> list[str]:
    flow = [
        "Store user preferences",
        "Generate initial outline",
        "Evaluate outline quality",
        "Repair outline if needed",
        "Render PowerPoint",
    ]

    if settings["upload_to_s3"]:
        flow.insert(1, "Backup source files")
        flow.append("Publish generated deck")

    if settings["enable_diagrams"]:
        insert_at = -1 if settings["upload_to_s3"] else len(flow)
        flow.insert(insert_at, "Add diagram slides")

    return flow


def render_flow(
    status_box: Any,
    flow_box: Any,
    progress: Any,
    flow: list[str],
    current: dict[str, str | None],
    completed: set[str],
) -> None:
    done = len(completed)
    progress.progress(done / max(len(flow), 1))

    current_step = current.get("step") or "Waiting to start"
    message = current.get("message") or "The agent is ready."

    status_box.markdown(
        f"""
        <div style="padding: 1.2rem; border-radius: 1rem; border: 1px solid #DDD;">
            <div style="font-size: 0.85rem; opacity: 0.7;">Current Agent Step</div>
            <div style="font-size: 1.35rem; font-weight: 700;">{current_step}</div>
            <div style="margin-top: 0.4rem; opacity: 0.8;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    items = []
    for step in flow:
        if step in completed:
            icon = "✓"
            opacity = "0.55"
            weight = "400"
        elif step == current.get("step"):
            icon = "●"
            opacity = "1"
            weight = "700"
        else:
            icon = "○"
            opacity = "0.45"
            weight = "400"

        items.append(
            f"""
            <div style="display:flex; gap:0.75rem; align-items:center; padding:0.55rem 0; opacity:{opacity};">
                <div style="width:1.4rem;">{icon}</div>
                <div style="font-weight:{weight};">{step}</div>
            </div>
            """
        )

    flow_box.markdown("".join(items), unsafe_allow_html=True)


def render_result(result: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Artifact")

    col1, col2, col3 = st.columns(3)
    col1.metric("Status", result.get("status", "unknown"))
    col2.metric("Slides", result.get("slide_count", 0))
    col3.metric("Warnings", len(result.get("warnings", [])))

    output_path = result.get("output_path")
    download_url = result.get("download_url")

    if output_path:
        path = Path(output_path)
        st.write(f"Local output: `{output_path}`")

        if path.exists():
            st.download_button(
                "Download PPTX",
                data=path.read_bytes(),
                file_name=path.name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )

    if download_url:
        st.link_button("Open S3 Download Link", download_url, use_container_width=True)

    if result.get("warnings"):
        with st.expander("Warnings"):
            for warning in result["warnings"]:
                st.warning(warning)

    with st.expander("Agent trace"):
        for item in result.get("trace", []):
            st.write(f"**{item.get('step')}** — `{item.get('status')}`")
            st.caption(item.get("observation", ""))


def save_uploads(uploaded_files: list[Any]) -> list[str]:
    TEMP_DIR.mkdir(exist_ok=True)
    paths = []

    for i, file in enumerate(uploaded_files, 1):
        path = TEMP_DIR / f"{i}_{safe_name(file.name)}"
        path.write_bytes(file.getbuffer())
        paths.append(str(path))

    return paths


def extract_content(uploaded_files: list[Any], image_model: str) -> str:
    texts = [text for text in process_uploaded_files(uploaded_files, image_model) if text and text.strip()]

    if not texts:
        raise ValueError("No readable content was extracted.")

    return "\n\n--- Source Break ---\n\n".join(texts)


def reset_files(uploaded_files: list[Any]) -> None:
    for file in uploaded_files:
        try:
            file.seek(0)
        except Exception:
            pass


def model_index(models: list[str], model: str) -> int:
    return models.index(model) if model in models else 0


def safe_name(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("_") or "uploaded_file"


if __name__ == "__main__":
    main()