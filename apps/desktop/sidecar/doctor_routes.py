from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request

from .contracts import DoctorPayload, DoctorResponse


def register_doctor_route(
    app: FastAPI,
    *,
    dependencies: list[Any],
    call_service: Callable[[Request, str], Any],
    request_id: Callable[[Request], str],
) -> None:
    @app.get(
        "/v1/doctor",
        response_model=DoctorResponse,
        dependencies=dependencies,
    )
    def get_doctor(request: Request) -> DoctorResponse:
        current_request_id = request_id(request)
        doctor = dict(call_service(request, "get_doctor"))
        persistence = request.app.state.query_task_manager.persistence_readiness()
        doctor.update(persistence)
        if not persistence["query_persistence_ready"]:
            doctor["ok"] = False
            doctor.update(
                {
                    "query_ready": False,
                    "query_issue_code": persistence["query_persistence_issue_code"],
                    "query_message": persistence["query_persistence_message"],
                    "query_action": persistence["query_persistence_action"],
                    "query_retryable": persistence["query_persistence_retryable"],
                }
            )
        return DoctorResponse(
            request_id=current_request_id,
            doctor=DoctorPayload.model_validate(
                {**doctor, "request_id": current_request_id}
            ),
        )
