import json
import os
import tempfile
from unittest.mock import MagicMock, patch


def _make_problem_set():
    return {
        "exam_id": "EXAM-TEST-001",
        "exam_date": "2026-04-18",
        "target_tags": ["TCP"],
        "mcq_section": [
            {
                "question_id": "q1",
                "tag": "TCP",
                "text": "关于 TCP 三次握手？",
                "options": {"A": "SYN", "B": "ACK", "C": "FIN", "D": "RST"},
                "correct_options": ["A", "B"],
                "explanation": "三次握手需要 SYN 和 ACK。",
                "brief_description": "TCP 握手",
            }
        ],
        "algorithm_section": [
            {
                "id": "algo-01",
                "title": "两数之和",
                "desc": "给定数组...",
                "constraints": "n <= 10^4",
                "sample_io": [{"input": "2\n2 7", "output": "0 1"}],
                "io_spec": {"type": "single_test_case"},
                "std_solution": "pass",
                "tag": "Algorithm",
                "brief_description": "两数之和",
                "source": "local",
            }
        ],
    }


def _make_app(tmpdir):
    ps = _make_problem_set()
    ps_path = os.path.join(tmpdir, "problem_set_20260418.json")
    with open(ps_path, "w", encoding="utf-8") as f:
        json.dump(ps, f, ensure_ascii=False)

    from server.app import create_app
    mock_settings = MagicMock()
    mock_settings.data_path = tmpdir
    mock_settings.api_key = "test-key"
    mock_settings.base_url = "http://test"
    mock_settings.model = "test-model"
    app = create_app(mock_settings)
    app.config["TESTING"] = True
    return app, ps


def test_index_returns_200_with_exam():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        with app.test_client() as client:
            resp = client.get("/")
    assert resp.status_code == 200
    assert b"TCP" in resp.data


def test_index_returns_404_when_no_problem_set():
    with tempfile.TemporaryDirectory() as tmpdir:
        from server.app import create_app
        mock_settings = MagicMock()
        mock_settings.data_path = tmpdir
        app = create_app(mock_settings)
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.get("/")
    assert resp.status_code == 404


def test_index_does_not_leak_answers():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        with app.test_client() as client:
            resp = client.get("/")
    content = resp.data.decode("utf-8")
    assert "correct_options" not in content
    assert "std_solution" not in content
    assert "三次握手需要 SYN 和 ACK" not in content


def test_grade_returns_result_page():
    with tempfile.TemporaryDirectory() as tmpdir:
        app, ps = _make_app(tmpdir)
        mock_report = [
            {"tag": "TCP", "score": 1.0, "brief_description": "TCP 握手"},
            {"tag": "Algorithm", "score": 0.85, "brief_description": "两数之和"},
        ]
        with patch("server.app.grade_submission", return_value=mock_report), \
             patch("server.app.update_mcq_stats"), \
             patch("server.app.generate_report"):
            with app.test_client() as client:
                resp = client.post(
                    "/grade",
                    json={
                        "mcq_answers": {"q1": ["A", "B"]},
                        "code_answers": {"algo-01": "def solve(): pass"},
                    },
                )
    assert resp.status_code == 200
    content = resp.data.decode("utf-8")
    assert "TCP" in content
