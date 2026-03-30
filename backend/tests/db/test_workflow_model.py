# backend/tests/db/test_workflow_model.py
import uuid

from app.db.models import Workflow, WorkflowRun


def test_workflow_create():
    user_id = uuid.uuid4()
    wf = Workflow.create(user_id=user_id, name="My Flow", dsl={"nodes": []})
    assert wf.user_id == user_id
    assert wf.name == "My Flow"
    assert wf.dsl == {"nodes": []}
    assert wf.id is not None


def test_workflow_run_start():
    wf_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run = WorkflowRun.start(workflow_id=wf_id, user_id=user_id)
    assert run.status == "running"
    assert run.workflow_id == wf_id
    assert run.started_at is not None


def test_workflow_run_complete():
    run = WorkflowRun.start(workflow_id=uuid.uuid4(), user_id=uuid.uuid4())
    run.complete(output={"result": "text"})
    assert run.status == "completed"
    assert run.output_data == {"result": "text"}
    assert run.completed_at is not None


def test_workflow_run_fail():
    run = WorkflowRun.start(workflow_id=uuid.uuid4(), user_id=uuid.uuid4())
    run.fail(error="timeout exceeded")
    assert run.status == "failed"
    assert run.error_message == "timeout exceeded"
    assert run.completed_at is not None
