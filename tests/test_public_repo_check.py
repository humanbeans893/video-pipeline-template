import importlib.util
import sys


def load_checker(repo_root):
    path = repo_root / "tools" / "public_repo_check.py"
    spec = importlib.util.spec_from_file_location("public_repo_check_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_secret_is_detected(tmp_path, repo_root):
    checker = load_checker(repo_root)
    secret = tmp_path / "note.txt"
    prefix = "ghp" + "_"
    secret.write_text("token=" + prefix + "abcdefghijklmnopqrstuvwxyz123456", encoding="utf-8")

    findings = checker.scan_files([secret], root=tmp_path)

    assert any("GitHub token" in finding.message for finding in findings)


def test_external_symlink_is_detected(tmp_path, repo_root):
    checker = load_checker(repo_root)
    outside = tmp_path.parent / "outside-public-check"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "outside"
    link.symlink_to(outside, target_is_directory=True)

    findings = checker.scan_files([link], root=tmp_path)

    assert any("outside" in finding.message for finding in findings)
