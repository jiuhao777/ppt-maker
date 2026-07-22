from pathlib import Path
from typing import Protocol


class VisionAdapter(Protocol):
    model_id: str

    def review(self, image: Path, prompt: str) -> str: ...


class TransformersPipelineAdapter:
    def __init__(
        self,
        model_id: str,
        *,
        trust_remote_code: bool = False,
        model_kwargs: dict | None = None,
    ):
        from transformers import pipeline

        self.model_id = model_id
        self._pipeline = pipeline(
            "image-text-to-text",
            model=model_id,
            trust_remote_code=trust_remote_code,
            device_map="auto",
            model_kwargs=model_kwargs or {},
        )

    def review(self, image: Path, prompt: str) -> str:
        from PIL import Image

        with Image.open(image) as source:
            picture = source.convert("RGB")
            picture.thumbnail((1600, 1600))
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": picture},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            output = self._pipeline(
                text=messages,
                max_new_tokens=512,
                do_sample=False,
            )
        generated = output[0]["generated_text"]
        if isinstance(generated, list):
            return str(generated[-1]["content"])
        return str(generated)
