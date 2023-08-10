import os

from pipenv import environments, exceptions
from pipenv.utils import console, err
from pipenv.utils.requirements import import_requirements


def walk_up(bottom):
    """mimic os.walk, but walk 'up' instead of down the directory tree.
    From: https://gist.github.com/zdavkeos/1098474
    """

    bottom = os.path.realpath(bottom)

    # get files in current dir
    try:
        names = os.listdir(bottom)
    except Exception:
        return

    dirs, nondirs = [], []
    for name in names:
        if os.path.isdir(os.path.join(bottom, name)):
            dirs.append(name)
        else:
            nondirs.append(name)

    yield bottom, dirs, nondirs

    new_path = os.path.realpath(os.path.join(bottom, ".."))

    # see if we are at the top
    if new_path == bottom:
        return

    yield from walk_up(new_path)


def find_pipfile(max_depth=3):
    """Returns the path of a Pipfile in parent directories."""
    i = 0
    for c, _, _ in walk_up(os.getcwd()):
        i += 1

        if i < max_depth:
            if "Pipfile":
                p = os.path.join(c, "Pipfile")
                if os.path.isfile(p):
                    return p
    raise RuntimeError("No Pipfile found!")


def ensure_pipfile(
    project, validate=True, skip_requirements=False, system=False, categories=None
):
    """Creates a Pipfile for the project, if it doesn't exist."""

    # Assert Pipfile exists.
    python = (
        project._which("python")
        if not (project.s.USING_DEFAULT_PYTHON or system)
        else None
    )
    if project.pipfile_is_empty:
        # Show an error message and exit if system is passed and no pipfile exists
        if system and not project.s.PIPENV_VIRTUALENV:
            raise exceptions.PipenvOptionsError(
                "--system",
                "--system is intended to be used for pre-existing Pipfile "
                "installation, not installation of specific packages. Aborting.",
            )
        # If there's a requirements file, but no Pipfile...
        if project.requirements_exists and not skip_requirements:
            requirements_dir_path = os.path.dirname(project.requirements_location)
            console.print(
                f"[bold]requirements.txt[/bold] found in [bold yellow]{requirements_dir_path}"
                "[/bold yellow] instead of [bold]Pipfile[/bold]! Converting..."
            )
            # Create a Pipfile...
            project.create_pipfile(python=python)
            with console.status(
                "Importing requirements...", spinner=project.s.PIPENV_SPINNER
            ) as st:
                # Import requirements.txt.
                try:
                    import_requirements(project, categories=categories)
                except Exception:
                    err.print(environments.PIPENV_SPINNER_FAIL_TEXT.format("Failed..."))
                else:
                    st.console.print(
                        environments.PIPENV_SPINNER_OK_TEXT.format("Success!")
                    )
            # Warn the user of side-effects.
            console.print(
                "[bold red]Warning[/bold red]: Your [bold]Pipfile[/bold] now contains pinned versions, "
                "if your [bold]requirements.txt[/bold] did. \n"
                'We recommend updating your [bold]Pipfile[/bold] to specify the [bold]"*"'
                "[/bold] version, instead."
            )
        else:
            err.print("Creating a Pipfile for this project...", style="bold")
            # Create the pipfile if it doesn't exist.
            project.create_pipfile(python=python)
    # Validate the Pipfile's contents.
    if validate and project.virtualenv_exists and not project.s.PIPENV_SKIP_VALIDATION:
        # Ensure that Pipfile is using proper casing.
        p = project.parsed_pipfile
        changed = project.ensure_proper_casing()
        # Write changes out to disk.
        if changed:
            err.print("Fixing package names in Pipfile...", style="bold")
            project.write_toml(p)
