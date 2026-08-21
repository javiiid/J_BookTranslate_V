from datetime import datetime, timezone
from pathlib import Path


UTC = timezone.utc


def log_progress(paths, message):
    """
    Write a timestamped progress message to the job log file
    and print it to the console.

    Expected paths:
        paths["progress_log"]
    """

    timestamp = datetime.now(UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    log_message = f"[{timestamp}] {message}"

    # Always show progress in console
    print(log_message)

    try:
        # ----------------------------------------------------
        # Get progress log path
        # ----------------------------------------------------

        log_file = paths.get("progress_log")

        if not log_file:
            raise KeyError(
                "Missing 'progress_log' in paths."
            )

        log_file = Path(log_file)

        # ----------------------------------------------------
        # Make sure parent directory exists
        # ----------------------------------------------------

        log_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Append log message
        # ----------------------------------------------------

        with open(
            log_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                log_message + "\n"
            )

    except Exception as e:

        print(
            f"Warning: Could not write "
            f"progress log: {e}"
        )