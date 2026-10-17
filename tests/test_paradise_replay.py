from datetime import datetime, timedelta, timezone

from backend.app import paradise_replay


def test_replay_frames_are_real_and_ordered():
    package = paradise_replay.snapshot()
    frames = package["frames"]
    assert package["summary"]["frame_count"] == 14
    assert package["summary"]["observation_frames"] == 9
    assert package["summary"]["detections"] == 2017
    assert package["summary"]["cells_observed"] == 591
    assert frames[0]["kind"] == "nist-window-start"
    assert frames[0]["observation_count"] == 0
    assert frames[-1]["observation_count"] == 20
    times = [datetime.fromisoformat(frame["at_utc"]) for frame in frames]
    assert times == sorted(times)
    assert all(frame["estimated"] is False for frame in frames)


def test_nist_frames_are_temporal_only_and_not_fabricated():
    package = paradise_replay.snapshot()
    nist_frames = [frame for frame in package["frames"] if frame["source_ids"] == ["nist-timeline"]]
    assert nist_frames
    for frame in nist_frames:
        assert frame["observation_count"] == 0
        assert frame["hotspot_cells"] == []
        assert frame["cumulative_detected_cells"] == []
        assert frame["data_status"] == "verified-window"
    active = next(frame for frame in package["frames"] if frame["nist_window"])
    assert active["nist_window"]["spatial_status"] == "not_digitized"


def test_replay_surfaces_the_observation_gap():
    package = paradise_replay.snapshot()
    assert package["summary"]["max_gap_minutes"] == 688
    gaps = [frame["gap_since_previous_minutes"] for frame in package["frames"]]
    assert 688 in gaps
    assert package["sources"]["weather"]["status"] == "missing"
    assert package["sources"]["nist"]["accepted_for_model_scoring"] is False


def test_seed_cells_use_only_past_observations():
    first = paradise_replay.frames()[5]
    seeds = set(paradise_replay.seed_cells_at(first["at_utc"]))
    assert seeds == set(first["cumulative_detected_cells"])
    assert seeds
    before_first = datetime.fromisoformat(first["at_utc"]) - timedelta(minutes=1)
    assert paradise_replay.seed_cells_at(before_first) == []


def test_frame_lookup_holds_the_last_real_frame():
    frames = paradise_replay.frames()
    target = datetime.fromisoformat(frames[6]["at_utc"]) + timedelta(minutes=20)
    assert paradise_replay.frame_at(target)["id"] == frames[6]["id"]
    after_end = datetime.fromisoformat(frames[-1]["at_utc"]) + timedelta(hours=2)
    assert paradise_replay.frame_at(after_end)["id"] == frames[-1]["id"]


def test_local_time_is_pacific_standard_time():
    frame = paradise_replay.frames()[5]
    local = datetime.fromisoformat(frame["at_local"])
    assert local.utcoffset() == timedelta(hours=-8)
    assert "PST" in frame["at_label"]


def test_replay_id_is_stable():
    assert paradise_replay.replay_id() == paradise_replay.replay_id()
    assert len(paradise_replay.replay_id()) == 16
    assert paradise_replay.snapshot()["data_version"]


def test_outside_grid_detections_are_counted_not_silently_dropped():
    package = paradise_replay.snapshot()
    observation_frames = [frame for frame in package["frames"] if frame["observation_count"] > 0]
    outside = sum(frame["outside_grid_count"] for frame in observation_frames)
    assert outside == package["summary"]["detections_outside_grid"]
    assert outside > 0
