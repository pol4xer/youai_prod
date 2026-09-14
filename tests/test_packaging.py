from importlib.metadata import entry_points, version

from youai import __version__
from youai.cli import main


def test_installed_distribution_exposes_the_console_script() -> None:
    scripts = entry_points(group="console_scripts", name="youai")

    assert version("youai") == __version__
    assert len(scripts) == 1
    assert next(iter(scripts)).load() is main
