from datetime import datetime, timezone
from pathlib import Path


UTC = timezone.utc


# ============================================================
# Directory Management
# ============================================================

def ensure_dir(name):
    """
    Create a directory relative to the project root.

    Parameters:
        name: Name of the directory to create.

    Returns:
        Path object pointing to the created/existing directory.
    """

    dir_path = (
        Path(__file__).resolve().parent.parent.parent
        / name
    )

    dir_path.mkdir(
        parents=True,
        exist_ok=True
    )

    return dir_path


# ============================================================
# Job ID
# ============================================================

def create_job_id(
    input_epub_path,
    from_lang,
    to_lang,
    model,
    timestamp=None
):
    """
    Create a unique job ID based on input parameters
    and timestamp.
    """

    if timestamp is None:
        timestamp = datetime.now(UTC).strftime(
            "%Y%m%d_%H%M%S"
        )

    base_name = Path(
        input_epub_path
    ).stem

    return (
        f"{base_name}_"
        f"{from_lang}_"
        f"{to_lang}_"
        f"{model}_"
        f"{timestamp}"
    )


# ============================================================
# Temporary Job Structure
# ============================================================

def ensure_temp_structure(job_id):
    """
    Create and return paths for all temporary job files.
    """

    temp_dir = ensure_dir("temp")

    job_dir = temp_dir / job_id

    job_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    paths = {
        "job_dir": job_dir,

        "state_file":
            job_dir / "job_state.json",

        "chunks_file":
            job_dir / "chunks.json",

        "translations_file":
            job_dir / "translations.json",

        "progress_log":
            job_dir / "progress.log",

        "events_log":
            job_dir / "events.jsonl",
        "system_prompt_file":
            job_dir / "system_prompt.txt",
    }

    return paths
