from video_pipeline.config import load_project


def test_example_project_loads(repo_root):
    project = load_project(repo_root)

    assert project.width == 1920
    assert project.height == 1080
    assert project.fps == 30
    assert len(project.lines) == 5
    assert set(project.speakers) == {"guide", "partner"}


def test_every_voice_has_credit(repo_root):
    project = load_project(repo_root)

    assert all(speaker["credit"].strip() for speaker in project.speakers.values())
