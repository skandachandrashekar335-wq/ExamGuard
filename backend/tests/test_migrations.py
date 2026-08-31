import os
import subprocess


class TestMigrations:
    def test_migration_file_exists(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
            "001_create_students_table.py",
        )
        assert os.path.exists(migration_path)

    def test_alembic_cfg_readable(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        assert os.path.exists(cfg_path)
        with open(cfg_path) as f:
            content = f.read()
        assert "script_location = alembic" in content
