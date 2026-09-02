import os
from typing import Any

os.environ.setdefault("GRADIO_SSR_MODE", "False")

import gradio as gr

from face_core import FaceApiError, embed_base64, embed_many_base64, match_base64, require_api_token

try:
    import spaces
except ImportError:
    spaces = None


def gpu_task(duration: int = 60):
    if spaces:
        return spaces.GPU(duration=duration)

    def decorator(fn):
        return fn

    return decorator


def scan_duration(frames: list[str], *_args) -> int:
    frame_count = max(1, min(len(frames or []), 5))
    return 8 + (frame_count * 4)


def health() -> dict:
    return {"success": True, "message": "AttendXsuite Gradio face API running"}


@gpu_task(duration=60)
def embed(image_base64: str, api_token: str, model: str | None = None) -> dict:
    try:
        require_api_token(api_token)
        return {"success": True, "data": embed_base64(image_base64, model)}
    except FaceApiError as error:
        return {"success": False, "detail": error.detail, "status_code": error.status_code}
    except Exception as error:
        return {"success": False, "detail": f"Face engine crashed: {error}", "status_code": 503}


@gpu_task(duration=scan_duration)
def embed_many(frames: list[str], api_token: str, model: str | None = None) -> dict:
    try:
        require_api_token(api_token)
        return {"success": True, "data": embed_many_base64((frames or [])[:5], model)}
    except FaceApiError as error:
        return {"success": False, "detail": error.detail, "status_code": error.status_code}
    except Exception as error:
        return {"success": False, "detail": f"Face engine crashed: {error}", "status_code": 503}


@gpu_task(duration=30)
def match(image_base64: str, employees: list[dict[str, Any]], api_token: str, threshold: float = 0.48, margin: float = 0.06) -> dict:
    try:
        require_api_token(api_token)
        return {"success": True, "data": match_base64(image_base64, employees, threshold, margin)}
    except FaceApiError as error:
        return {"success": False, "detail": error.detail, "status_code": error.status_code}
    except Exception as error:
        return {"success": False, "detail": f"Face engine crashed: {error}", "status_code": 503}


with gr.Blocks(title="AttendXsuite Face API") as demo:
    gr.Markdown("# AttendXsuite Face API")
    gr.Markdown("Use the named API endpoints from the AttendXsuite backend.")

    health_output = gr.JSON(label="Health")
    gr.Button("Health").click(fn=health, inputs=[], outputs=health_output, api_name="health")

    with gr.Accordion("Embed API", open=False):
        embed_image_input = gr.Textbox(label="Image base64")
        embed_token_input = gr.Textbox(label="API token", type="password")
        embed_model_input = gr.Textbox(label="Model", value=os.getenv("HF_FACE_MODEL", "buffalo_s"))
        embed_output = gr.JSON(label="Embedding")
        gr.Button("Embed").click(
            fn=embed,
            inputs=[embed_image_input, embed_token_input, embed_model_input],
            outputs=embed_output,
            api_name="embed",
        )

    with gr.Accordion("Match API", open=False):
        match_image_input = gr.Textbox(label="Image base64")
        match_employees_input = gr.JSON(label="Employees")
        match_token_input = gr.Textbox(label="API token", type="password")
        match_threshold_input = gr.Number(label="Threshold", value=0.48)
        match_margin_input = gr.Number(label="Margin", value=0.06)
        match_output = gr.JSON(label="Match")
        gr.Button("Match").click(
            fn=match,
            inputs=[match_image_input, match_employees_input, match_token_input, match_threshold_input, match_margin_input],
            outputs=match_output,
            api_name="match",
        )

    with gr.Accordion("Batch Embed API", open=False):
        batch_frames_input = gr.JSON(label="Frames")
        batch_token_input = gr.Textbox(label="API token", type="password")
        batch_model_input = gr.Textbox(label="Model", value=os.getenv("HF_FACE_MODEL", "buffalo_s"))
        batch_output = gr.JSON(label="Embeddings")
        gr.Button("Embed Frames").click(
            fn=embed_many,
            inputs=[batch_frames_input, batch_token_input, batch_model_input],
            outputs=batch_output,
            api_name="embed_many",
        )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        ssr_mode=False,
        pwa=False,
    )
