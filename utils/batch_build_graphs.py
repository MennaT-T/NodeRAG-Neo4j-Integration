#!/usr/bin/env python3
"""
Batch user graph builder for NodeRAG API.

Automates this sequence per user in strict order:
1) Upload resume via /documents
2) Trigger build via /build
3) Poll /build/{build_id}/status until completed/failed/timeout

Designed for long-running builds (e.g., 15+ minutes per user) with:
- HTTP retry with backoff
- per-user timeout
- continue-or-stop behavior on failures
- final JSON report
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests import Response
from requests.exceptions import RequestException


@dataclass
class UserTask:
    user_id: str
    resume_path: Path
    document_type: str = "resume"
    filename: Optional[str] = None


@dataclass
class UserResult:
    user_id: str
    resume_path: str
    success: bool
    stage: str
    started_at: str
    ended_at: str
    duration_seconds: float
    build_id: Optional[str] = None
    build_status: Optional[str] = None
    build_stage: Optional[str] = None
    error: Optional[str] = None


class ApiClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        timeout_seconds: int,
        max_retries: int,
        retry_backoff_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def _request_with_retry(self, method: str, endpoint: str, **kwargs: Any) -> Response:
        url = f"{self.base_url}{endpoint}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method=method, url=url, timeout=self.timeout_seconds, **kwargs)

                # Retry only transient/server-side responses.
                if response.status_code >= 500:
                    last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
                else:
                    return response
            except RequestException as exc:
                last_error = exc

            if attempt < self.max_retries:
                sleep_time = self.retry_backoff_seconds * attempt
                time.sleep(sleep_time)

        if last_error is None:
            raise RuntimeError(f"Request failed with no error details: {method} {url}")
        raise RuntimeError(f"Request failed after retries: {method} {url} :: {last_error}")

    def get_json(self, endpoint: str, expected_status: int = 200) -> Dict[str, Any]:
        response = self._request_with_retry("GET", endpoint)
        self._raise_unexpected(response, expected_status)
        return response.json()

    def post_json(self, endpoint: str, payload: Dict[str, Any], expected_status: int = 200) -> Dict[str, Any]:
        response = self._request_with_retry("POST", endpoint, json=payload)
        self._raise_unexpected(response, expected_status)
        return response.json()

    def post_file(
        self,
        endpoint: str,
        *,
        file_path: Path,
        document_type: str,
        user_id: str,
        filename: Optional[str],
        expected_status: int = 200,
    ) -> Dict[str, Any]:
        with file_path.open("rb") as handle:
            files = {"file": (file_path.name, handle)}
            data = {
                "document_type": document_type,
                "user_id": user_id,
            }
            if filename:
                data["filename"] = filename

            response = self._request_with_retry("POST", endpoint, files=files, data=data)
            self._raise_unexpected(response, expected_status)
            return response.json()

    @staticmethod
    def _raise_unexpected(response: Response, expected_status: int) -> None:
        if response.status_code != expected_status:
            snippet = response.text[:1000]
            raise RuntimeError(
                f"Unexpected status {response.status_code} (expected {expected_status}): {snippet}"
            )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_tasks(mapping_csv: Optional[Path], resumes_dir: Optional[Path]) -> List[UserTask]:
    if mapping_csv:
        return load_tasks_from_csv(mapping_csv)
    if resumes_dir:
        return load_tasks_from_folder(resumes_dir)
    raise ValueError("Provide either --mapping-csv or --resumes-dir")


def load_tasks_from_csv(mapping_csv: Path) -> List[UserTask]:
    if not mapping_csv.exists():
        raise FileNotFoundError(f"Mapping CSV not found: {mapping_csv}")

    tasks: List[UserTask] = []
    with mapping_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"user_id", "resume_path"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        for idx, row in enumerate(reader, start=2):
            user_id = (row.get("user_id") or "").strip()
            resume_path_raw = (row.get("resume_path") or "").strip()
            if not user_id or not resume_path_raw:
                raise ValueError(f"CSV row {idx} missing user_id or resume_path")

            resume_path = Path(resume_path_raw).expanduser().resolve()
            document_type = (row.get("document_type") or "resume").strip() or "resume"
            filename = (row.get("filename") or "").strip() or None

            tasks.append(
                UserTask(
                    user_id=user_id,
                    resume_path=resume_path,
                    document_type=document_type,
                    filename=filename,
                )
            )

    return tasks


def load_tasks_from_folder(resumes_dir: Path) -> List[UserTask]:
    if not resumes_dir.exists() or not resumes_dir.is_dir():
        raise FileNotFoundError(f"Resumes directory not found: {resumes_dir}")

    allowed_ext = {".pdf", ".docx", ".txt"}
    tasks: List[UserTask] = []
    for path in sorted(resumes_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in allowed_ext:
            tasks.append(UserTask(user_id=path.stem, resume_path=path.resolve(), document_type="resume"))

    if not tasks:
        raise ValueError(f"No resume files found in {resumes_dir} (expected pdf/docx/txt)")

    return tasks


def verify_inputs(tasks: Iterable[UserTask]) -> None:
    seen = set()
    for task in tasks:
        if task.user_id in seen:
            raise ValueError(f"Duplicate user_id found: {task.user_id}")
        seen.add(task.user_id)

        if not task.resume_path.exists() or not task.resume_path.is_file():
            raise FileNotFoundError(f"Resume not found for user {task.user_id}: {task.resume_path}")


def wait_for_api(client: ApiClient, wait_timeout_seconds: int = 180) -> None:
    start = time.time()
    while True:
        try:
            health = client.get_json("/health", expected_status=200)
            if health.get("success"):
                return
        except Exception:
            pass

        if time.time() - start > wait_timeout_seconds:
            raise TimeoutError("API health check timed out")

        time.sleep(3)


def wait_for_build_completion(
    client: ApiClient,
    build_id: str,
    poll_interval_seconds: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    start = time.time()

    while True:
        status_payload = client.get_json(f"/build/{build_id}/status", expected_status=200)
        status = status_payload.get("status")

        if status == "completed":
            return status_payload

        if status == "failed":
            raise RuntimeError(
                f"Build {build_id} failed: {status_payload.get('error_details') or status_payload}"
            )

        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Build {build_id} timed out after {timeout_seconds} seconds")

        current_stage = status_payload.get("current_stage") or "unknown"
        print(f"  - build_id={build_id} status={status} stage={current_stage}")
        time.sleep(poll_interval_seconds)


def process_user(
    client: ApiClient,
    task: UserTask,
    *,
    incremental: Optional[bool],
    sync_to_neo4j: Optional[bool],
    force_rebuild: Optional[bool],
    poll_interval_seconds: int,
    build_timeout_seconds: int,
) -> UserResult:
    started = now_iso()
    started_ts = time.time()

    print(f"\n=== User {task.user_id} ===")
    print(f"Resume: {task.resume_path}")

    try:
        print("1/3 Uploading document...")
        upload_payload = client.post_file(
            "/documents",
            file_path=task.resume_path,
            document_type=task.document_type,
            user_id=task.user_id,
            filename=task.filename,
            expected_status=200,
        )
        if not upload_payload.get("success"):
            raise RuntimeError(f"Upload failed response: {upload_payload}")

        print("2/3 Starting build...")
        # Match the known-good API behavior: send only user_id by default.
        # Optional build flags are sent only if explicitly requested via CLI.
        build_request_payload: Dict[str, Any] = {
            "user_id": task.user_id,
        }
        if incremental is not None:
            build_request_payload["incremental"] = incremental
        if sync_to_neo4j is not None:
            build_request_payload["sync_to_neo4j"] = sync_to_neo4j
        if force_rebuild is not None:
            build_request_payload["force_rebuild"] = force_rebuild

        build_payload = client.post_json(
            "/build",
            payload=build_request_payload,
            expected_status=200,
        )
        if not build_payload.get("success"):
            raise RuntimeError(f"Build start failed response: {build_payload}")

        build_id = build_payload.get("build_id")
        if not build_id:
            raise RuntimeError(f"No build_id returned: {build_payload}")

        print(f"3/3 Waiting for build completion... build_id={build_id}")
        status_payload = wait_for_build_completion(
            client,
            build_id=build_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=build_timeout_seconds,
        )

        ended = now_iso()
        duration = time.time() - started_ts
        print(f"Completed user {task.user_id} in {duration/60:.1f} minutes")

        return UserResult(
            user_id=task.user_id,
            resume_path=str(task.resume_path),
            success=True,
            stage="completed",
            started_at=started,
            ended_at=ended,
            duration_seconds=duration,
            build_id=build_id,
            build_status=status_payload.get("status"),
            build_stage=status_payload.get("current_stage"),
        )

    except Exception as exc:
        ended = now_iso()
        duration = time.time() - started_ts
        print(f"Failed user {task.user_id}: {exc}")
        return UserResult(
            user_id=task.user_id,
            resume_path=str(task.resume_path),
            success=False,
            stage="failed",
            started_at=started,
            ended_at=ended,
            duration_seconds=duration,
            error=str(exc),
        )


def write_report(output_path: Path, results: List[UserResult], total_seconds: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    payload = {
        "generated_at": now_iso(),
        "total_users": len(results),
        "success_count": success_count,
        "failure_count": fail_count,
        "total_duration_seconds": total_seconds,
        "results": [asdict(r) for r in results],
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch build per-user NodeRAG graphs")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument(
        "--api-key",
        default=os.getenv("NODERAG_API_KEY", ""),
        help="NodeRAG API key (or set NODERAG_API_KEY env var)",
    )

    parser.add_argument("--mapping-csv", type=Path, default=None, help="CSV with user_id,resume_path")
    parser.add_argument("--resumes-dir", type=Path, default=None, help="Folder mode: user_id from filename stem")

    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override incremental build behavior (default: use API default)",
    )
    parser.add_argument(
        "--sync-to-neo4j",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override Neo4j sync behavior (default: use API default)",
    )
    parser.add_argument(
        "--force-rebuild",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override force rebuild behavior (default: use API default)",
    )

    parser.add_argument("--http-timeout", type=int, default=90, help="HTTP timeout per request in seconds")
    parser.add_argument("--http-retries", type=int, default=3, help="HTTP retries for transient errors")
    parser.add_argument("--retry-backoff", type=float, default=3.0, help="Backoff base seconds")

    parser.add_argument("--poll-interval", type=int, default=20, help="Build status polling interval")
    parser.add_argument("--build-timeout-min", type=int, default=120, help="Per-user build timeout")

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining users if one fails",
    )

    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("POC_Data") / "logs" / "batch_build_report.json",
        help="Path to write JSON report",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        tasks = load_tasks(args.mapping_csv, args.resumes_dir)
        verify_inputs(tasks)
    except Exception as exc:
        print(f"Input validation failed: {exc}")
        return 2

    if not args.api_key:
        print("Warning: API key is empty. Protected endpoints may fail with 401.")

    client = ApiClient(
        base_url=args.api_url,
        api_key=args.api_key,
        timeout_seconds=args.http_timeout,
        max_retries=max(args.http_retries, 1),
        retry_backoff_seconds=max(args.retry_backoff, 0.1),
    )

    print(f"Loaded {len(tasks)} users")
    print("Waiting for API health...")
    try:
        wait_for_api(client)
    except Exception as exc:
        print(f"API is not ready: {exc}")
        return 3

    results: List[UserResult] = []
    batch_start = time.time()
    build_timeout_seconds = max(args.build_timeout_min, 1) * 60

    for idx, task in enumerate(tasks, start=1):
        print(f"\n[{idx}/{len(tasks)}] Processing user_id={task.user_id}")

        result = process_user(
            client,
            task,
            incremental=args.incremental,
            sync_to_neo4j=args.sync_to_neo4j,
            force_rebuild=args.force_rebuild,
            poll_interval_seconds=max(args.poll_interval, 3),
            build_timeout_seconds=build_timeout_seconds,
        )
        results.append(result)

        if not result.success and not args.continue_on_error:
            print("Stopping batch due to failure. Use --continue-on-error to process all users.")
            break

    total_seconds = time.time() - batch_start
    write_report(args.report_json, results, total_seconds)

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    print("\n=== Batch Summary ===")
    print(f"Users processed: {len(results)}")
    print(f"Succeeded: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Total duration: {total_seconds/60:.1f} minutes")
    print(f"Report: {args.report_json}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
