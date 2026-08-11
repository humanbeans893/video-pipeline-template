from video_pipeline.cli import main


def test_validate_command(repo_root):
    assert main(["--root", str(repo_root), "validate"]) == 0
