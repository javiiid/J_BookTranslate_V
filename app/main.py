import sys
from pathlib import Path

from openai import OpenAI

from app.cli.parser import parse_args
from app.pipeline.pipeline import translate
from app.jobs.manager import find_resumable_jobs
from app.core.paths import ensure_dir
from app.core.config import read_config


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    """
    Main entry point for J Book Translate.

    Responsibilities:
        1. Parse command-line arguments.
        2. Validate input file.
        3. Determine file type.
        4. Find resumable jobs when requested.
        5. Load API configuration.
        6. Create the API client with custom base URL.
        7. Determine output path.
        8. Start the translation pipeline.
        9. Handle user interruption and errors.
    """

    try:

        # ====================================================
        # 1. Parse command-line arguments
        # ====================================================

        args = parse_args()

        print("=" * 60)
        print("J Book Translate")
        print("=" * 60)

        print(f"Input    : {args.input}")
        print(f"Output   : {args.output}")
        print(f"From     : {args.from_lang}")
        print(f"To       : {args.to_lang}")
        print(f"Model    : {args.model}")
        print(f"Mode     : {args.mode}")
        print("=" * 60)

        # ====================================================
        # 2. Validate input file
        # ====================================================

        input_path = Path(args.input)

        if not input_path.exists():

            print(
                f"Error: Input file not found:\n"
                f"{args.input}"
            )

            sys.exit(1)

        if not input_path.is_file():

            print(
                f"Error: Input path is not a file:\n"
                f"{args.input}"
            )

            sys.exit(1)

        # ====================================================
        # 3. Detect file type
        # ====================================================

        filetype = (
            input_path
            .suffix
            .lower()
            .lstrip(".")
        )

        if filetype not in ["epub", "pdf"]:

            print(
                "Error: Input file must be "
                "an EPUB or PDF file."
            )

            sys.exit(1)

        print(
            f"File type: {filetype}"
        )

        # ====================================================
        # 4. Find resumable job
        # ====================================================

        job_id = None

        if args.mode in [
            "resume",
            "resumebatch"
        ]:

            print()
            print(
                "Looking for resumable "
                "translation jobs..."
            )

            resumable_jobs = find_resumable_jobs(
                args.input,
                args.from_lang,
                args.to_lang,
                args.model
            )

            if resumable_jobs:

                print()
                print(
                    "Found resumable "
                    "translation jobs:"
                )

                for i, (
                    resumable_job_id,
                    timestamp,
                    state
                ) in enumerate(
                    resumable_jobs,
                    1
                ):

                    print(
                        f"{i}. Job from {timestamp}"
                    )

                    print(
                        f"   Progress: "
                        f"{state['chunks_completed']}/"
                        f"{state['chunks_total']} chunks"
                    )

                    print(
                        f"   Last updated: "
                        f"{state['last_updated']}"
                    )

                # --------------------------------------------
                # Ask user which job to resume
                # --------------------------------------------

                while True:

                    choice = input(
                        "\nEnter job number "
                        "to resume "
                        "(or 'n' for new job, "
                        "'q' to quit): "
                    ).strip()

                    if choice.lower() == "n":

                        job_id = None
                        break

                    if choice.lower() == "q":

                        print("Aborting.")
                        sys.exit(0)

                    try:

                        index = int(choice) - 1

                        if 0 <= index < len(
                            resumable_jobs
                        ):

                            job_id = (
                                resumable_jobs[
                                    index
                                ][0]
                            )

                            break

                    except ValueError:
                        pass

                    print(
                        "Invalid choice. "
                        "Please try again."
                    )

            else:

                print(
                    "No resumable jobs found."
                )

                if args.mode == "resumebatch":

                    print(
                        "Please run with "
                        "--mode batch first."
                    )

                    sys.exit(1)

                choice = input(
                    "Start a new translation job? "
                    "(y/N): "
                ).strip()

                if choice.lower() != "y":

                    print("Aborting.")
                    sys.exit(0)

                job_id = None

        # ====================================================
        # 5. Load API configuration
        # ====================================================

        config = read_config()

        openai_config = config.get(
            "openai",
            {}
        )

        api_key = openai_config.get(
            "api_key"
        )

        base_url = openai_config.get(
            "base_url"
        )

        # ----------------------------------------------------
        # Validate API key
        # ----------------------------------------------------

        if not api_key:

            print(
                "Error: API key is not configured."
            )

            print(
                "Please check config.yaml:"
            )

            print(
                "openai:"
            )

            print(
                "  api_key: YOUR_API_KEY"
            )

            sys.exit(1)

        # ----------------------------------------------------
        # Validate base URL
        # ----------------------------------------------------

        if not base_url:

            print(
                "Error: API base URL is not configured."
            )

            print(
                "Please check config.yaml:"
            )

            print(
                "openai:"
            )

            print(
                "  base_url: https://api.gapgpt.app/v1"
            )

            sys.exit(1)

        # ====================================================
        # 6. Create API client
        # ====================================================

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        print(
            f"API client initialized."
        )

        print(
            f"API base URL: {base_url}"
        )

        # ====================================================
        # 7. Determine output path
        # ====================================================

        if args.output:

            output_path_obj = Path(
                args.output
            )

            # --------------------------------------------
            # User provided an existing directory
            # --------------------------------------------

            if (
                output_path_obj.exists()
                and output_path_obj.is_dir()
            ):

                output_filename = (
                    f"{input_path.stem}_"
                    f"{args.to_lang.lower()}_"
                    f"{args.model}."
                    f"{filetype}"
                )

                output_path_obj = (
                    output_path_obj
                    / output_filename
                )

            # --------------------------------------------
            # Create parent directory
            # --------------------------------------------

            output_path_obj.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            output_path = str(
                output_path_obj
            )

        else:

            # --------------------------------------------
            # Default output directory
            # --------------------------------------------

            output_dir = ensure_dir(
                "output"
            )

            output_filename = (
                f"{input_path.stem}_"
                f"{args.to_lang.lower()}_"
                f"{args.model}."
                f"{filetype}"
            )

            output_path_obj = (
                output_dir
                / output_filename
            )

            output_path = str(
                output_path_obj
            )

        print(
            f"Output file: {output_path}"
        )

        # ====================================================
        # 8. Start translation
        # ====================================================

        print()
        print("=" * 60)
        print("Starting translation...")
        print("=" * 60)

        translate(
            client,
            args.input,
            output_path,
            args.from_lang,
            args.to_lang,
            mode=args.mode,
            model=args.model,
            fast=(
                args.mode
                not in [
                    "batch",
                    "batchcheck",
                    "resumebatch"
                ]
            ),
            resume_job_id=job_id,
            debug=args.debug,
            filetype=filetype
        )

        # ====================================================
        # 9. Finished
        # ====================================================

        print()
        print("=" * 60)
        print(
            "Translation process finished."
        )
        print("=" * 60)

    # ========================================================
    # USER INTERRUPT
    # ========================================================

    except KeyboardInterrupt:

        print()
        print("=" * 60)
        print(
            "TRANSLATION INTERRUPTED"
        )
        print("=" * 60)

        print(
            "The translation was interrupted "
            "by the user."
        )

        print(
            "Completed translations were saved."
        )

        print(
            "Run again with --mode resume "
            "to continue."
        )

        print("=" * 60)

        sys.exit(130)

    # ========================================================
    # APPLICATION ERROR
    # ========================================================

    except Exception as e:

        print()
        print("=" * 60)
        print("ERROR")
        print("=" * 60)

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        raise


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()