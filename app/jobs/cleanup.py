import os
from pathlib import Path

def chmod_recursive(path):
    """
    Recursively change permissions of a directory and all its contents.

    This is mainly used before cleanup to make sure files and directories
    can be deleted without permission-related errors.
    """

    try:
        # Give the main path full permissions
        os.chmod(path, 0o777)

        # If the path is a directory, process everything inside it
        if os.path.isdir(path):

            # Walk through all subdirectories and files recursively
            for root, dirs, files in os.walk(path):

                # Change permissions of every subdirectory
                for d in dirs:
                    os.chmod(
                        os.path.join(root, d),
                        0o777
                    )

                # Change permissions of every file
                for f in files:
                    os.chmod(
                        os.path.join(root, f),
                        0o777
                    )

    except Exception as e:
        # Permission errors should not completely stop the program.
        # Instead, display a warning and continue execution.
        print(
            f"Warning: Failed to change permissions for "
            f"{path}: {e} [chmod_recursive]"
        )


def cleanup_files(client, file_ids, temp_dir=None, keep_temp=False):
    """
    Clean up temporary files, job directories, and uploaded OpenAI files.

    Parameters:
        client:
            OpenAI API client used to delete uploaded files.

        file_ids:
            List of OpenAI file IDs that should be deleted.

        temp_dir:
            Specific temporary directory belonging to the current job.

        keep_temp:
            If True, temporary files are preserved for debugging/resume.
            If False, temporary files are deleted after processing.
    """

    # Display whether temporary files should be preserved
    print(
        f"Cleanup called with keep_temp={keep_temp} "
        f"for job dir: {temp_dir.name} [cleanup_files]"
    )

    # If keep_temp=True, stop cleanup immediately.
    # This is useful when we need the temporary files for debugging
    # or resuming an interrupted translation job.
    if keep_temp:
        print(
            f"Keeping job directory: {temp_dir} [cleanup_files]"
        )
        return

    # Make sure a temporary directory exists before trying to clean it
    if not keep_temp and temp_dir and temp_dir.exists():

        try:
            print(
                f"\nStarting cleanup of job directory: "
                f"{temp_dir.name} [cleanup_files]"
            )

            # Make sure all files/directories have sufficient permissions
            # before attempting to delete them.
            chmod_recursive(temp_dir)

            # Iterate over all items directly inside the job directory
            for item in temp_dir.glob('*'):

                # Only process files at this level
                if item.is_file():

                    try:
                        # Try to open the file first.
                        # This is intended to help with open-file handling.
                        with open(item, 'r') as f:

                            try:
                                # Force buffered data to be synchronized
                                # with the filesystem.
                                os.fsync(f.fileno())

                            except:
                                # Ignore fsync failures because they are
                                # not critical for the cleanup operation.
                                pass

                        # Delete the file if it exists
                        item.unlink(missing_ok=True)

                    except Exception as e:
                        # If one file cannot be deleted, report the problem
                        # but continue cleaning the remaining files.
                        print(
                            f"Warning: Could not remove file "
                            f"{item}: {e} [cleanup_files]"
                        )

            # After deleting the files, try to remove the empty job directory
            try:
                temp_dir.rmdir()

                print(
                    f"Removed job directory: "
                    f"{temp_dir.name} [cleanup_files]"
                )

            except Exception as e:
                # The directory may still contain files or be locked
                print(
                    f"Warning: Could not remove job directory "
                    f"{temp_dir.name}: {e} [cleanup_files]"
                )

        except Exception as e:
            # Catch unexpected cleanup errors so that cleanup failure
            # does not crash the entire application.
            print(
                f"Warning: Error during cleanup: "
                f"{e} [cleanup_files]"
            )

    # ========================================================
    # Delete Uploaded OpenAI Files
    # ========================================================

    # Iterate through all OpenAI file IDs associated with this job
    for file_id in file_ids:

        try:
            # Delete the uploaded file from OpenAI
            client.files.delete(file_id)

            print(
                f"Deleted OpenAI file: "
                f"{file_id} [cleanup_files]"
            )

        except Exception as e:
            # If deletion fails, show a warning but continue.
            print(
                f"Warning: Failed to delete OpenAI file "
                f"{file_id}: {e} [cleanup_files]"
            )


