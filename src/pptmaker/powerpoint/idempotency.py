import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse


class IdempotencyConflict(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_fingerprint(request: RenderRequest) -> str:
    digest = hashlib.sha256()
    input_path = Path(request.input_path)
    digest.update(input_path.read_bytes())
    stable = {
        "run_id": request.run_id,
        "input_path": str(input_path.resolve()),
        "output_dir": str(Path(request.output_dir).resolve()),
    }
    digest.update(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


class IdempotencyJournal:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        name = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{name}.json"

    def _read(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text("utf-8"))

    def _write(self, key: str, payload: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        temporary = path.with_suffix(f".tmp-{uuid4().hex}")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def lookup(self, key: str, fingerprint: str) -> RenderResponse | None:
        record = self._read(key)
        if record is None:
            return None
        if record["fingerprint"] != fingerprint:
            raise IdempotencyConflict(
                "idempotency key was already used for a different request"
            )
        if record["state"] != "completed":
            return None
        response = RenderResponse.model_validate(record["response"])
        if not response.slide_images or not all(
            Path(path).is_file() for path in response.slide_images
        ):
            return None
        return response.model_copy(
            update={"details": {**response.details, "idempotent_replay": True}}
        )

    def claim(self, key: str, fingerprint: str) -> None:
        record = self._read(key)
        if record is not None and record["fingerprint"] != fingerprint:
            raise IdempotencyConflict(
                "idempotency key was already used for a different request"
            )
        self._write(
            key,
            {
                "fingerprint": fingerprint,
                "state": "running",
                "updated_at": _utc_now(),
            },
        )

    def complete(
        self,
        key: str,
        fingerprint: str,
        response: RenderResponse,
    ) -> None:
        self._write(
            key,
            {
                "fingerprint": fingerprint,
                "state": "completed",
                "updated_at": _utc_now(),
                "response": response.model_dump(mode="json"),
            },
        )

    def fail(self, key: str, fingerprint: str, error: str) -> None:
        self._write(
            key,
            {
                "fingerprint": fingerprint,
                "state": "failed",
                "updated_at": _utc_now(),
                "error": error,
            },
        )
