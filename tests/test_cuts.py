from video_pipeline.config import load_project
from video_pipeline.timeline import validate_cut_contract


def test_example_cuts_match_script(repo_root):
    project = load_project(repo_root)
    cuts = validate_cut_contract(project)

    assert set(cuts) == {"01", "02", "03"}
    assert cuts["02"].kind == "movie"
