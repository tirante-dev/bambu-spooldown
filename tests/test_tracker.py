from spooldown.tracker import Job, Tracker

AMS = {
    "ams": [
        {
            "id": "0",
            "tray": [
                {"id": "0", "tray_uuid": "9DA7B1759BC4450C8500EBDAFA82D24A"},
                {"id": "1", "tray_uuid": "26CE629599EE4D2E88E2C4904CC0D22F"},
                {"id": "2", "tray_uuid": "4F10CEC7DEEC44F4A98359B717FB040D"},
                {"id": "3", "tray_uuid": "00000000000000000000000000000000"},
            ],
        }
    ]
}


def collect() -> tuple[list[tuple[Job, float]], Tracker]:
    done: list[tuple[Job, float]] = []
    return done, Tracker(lambda job, fraction: done.append((job, fraction)))


def push_full(t: Tracker, **overrides: object) -> None:
    state: dict[str, object] = {
        "gcode_state": "RUNNING",
        "task_id": "123",
        "subtask_name": "widget",
        "gcode_file": "/data/Metadata/plate_1.gcode",
        "print_type": "cloud",
        "mapping": [0],
        "mc_percent": 1,
        "ams": AMS,
    }
    state.update(overrides)
    t.handle({"print": state})


def test_finish_emits_full_fraction() -> None:
    done, t = collect()
    push_full(t)
    t.handle({"print": {"mc_percent": 55}})
    t.handle({"print": {"gcode_state": "FINISH"}})
    assert len(done) == 1
    job, fraction = done[0]
    assert fraction == 1.0
    assert job.task_id == "123"
    assert job.mapping == [0]
    assert job.tray_uuids[0] == "9DA7B1759BC4450C8500EBDAFA82D24A"


def test_failed_emits_percent_fraction() -> None:
    done, t = collect()
    push_full(t)
    t.handle({"print": {"mc_percent": 40}})
    t.handle({"print": {"gcode_state": "FAILED"}})
    assert done[0][1] == 0.40


def test_job_first_seen_running_is_marked_unseen_start() -> None:
    done, t = collect()
    push_full(t, mc_percent=80)
    t.handle({"print": {"gcode_state": "FINISH"}})
    assert done[0][0].seen_start is False


def test_terminal_without_active_history_emits_nothing() -> None:
    done, t = collect()
    t.handle({"print": {"gcode_state": "FINISH", "task_id": "9"}})
    assert done == []


def test_new_task_id_starts_new_job() -> None:
    done, t = collect()
    push_full(t)
    t.handle({"print": {"gcode_state": "FINISH"}})
    push_full(t, task_id="124", mapping=[2])
    t.handle({"print": {"gcode_state": "FINISH"}})
    assert [j.task_id for j, _ in done] == ["123", "124"]
    assert done[1][0].mapping == [2]
