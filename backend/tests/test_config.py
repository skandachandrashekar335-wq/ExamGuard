import os
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings


class TestConfig:
    def test_project_root_points_to_examguard_root(self):
        assert PROJECT_ROOT.name == "ExamGuard"
        assert (PROJECT_ROOT / "backend").is_dir()
        assert (PROJECT_ROOT / "frontend").is_dir()

    def test_env_file_path_is_absolute(self):
        settings = get_settings()
        env_path = settings.model_config["env_file"]
        assert isinstance(env_path, Path)
        assert env_path.is_absolute()

    def test_env_file_resolves_regardless_of_cwd(self):
        original_cwd = os.getcwd()
        try:
            os.chdir(PROJECT_ROOT / "backend" / "app" / "core")
            from importlib import reload

            import app.core.config as cfg

            reload(cfg)
            reloaded_settings = cfg.Settings()
            env_path = reloaded_settings.model_config["env_file"]
            assert env_path.is_absolute()
            assert env_path.name == ".env"
            assert str(env_path).endswith("ExamGuard\\.env")
        finally:
            os.chdir(original_cwd)
