# ============================================================
# app/main.py
# ============================================================

import sys
from pathlib import Path

from openai import OpenAI

from app.cli.parser import parse_args
from app.pipeline.pipeline import translate
from app.jobs.manager import find_resumable_jobs
from app.core.paths import ensure_dir
from app.core.config import read_config
from app.translation.prompts import get_translation_prompt
from app.output.formats import (
    available_output_formats,
    normalize_outputs,
)


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    """
    Main entry point for KALIMA.

    Responsibilities:
        1. Parse command-line arguments.
        2. Validate input file.
        3. Detect file type.
        4. Find resumable jobs when requested.
        5. Load API configuration.
        6. Create OpenAI-compatible API client.
        7. Determine output path.
        8. Get translation prompt from the user.
        9. Start the translation pipeline.
        10. Handle user interruption.
        11. Handle application errors.
    """

    try:

        # ====================================================
        # 1. Parse command-line arguments
        # ====================================================

        args = parse_args()

        print()
        print("=" * 60)
        print("KALIMA")
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

            print()
            print("ERROR")
            print("-" * 60)
            print("Input file not found:")
            print(args.input)
            print("-" * 60)

            sys.exit(1)

        if not input_path.is_file():

            print()
            print("ERROR")
            print("-" * 60)
            print("Input path is not a file:")
            print(args.input)
            print("-" * 60)

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

        if filetype not in {"epub", "pdf", "srt"}:

            print()
            print("ERROR")
            print("-" * 60)
            print("Input file must be an EPUB, PDF or SRT file.")
            print("-" * 60)

            sys.exit(1)

        print(f"File type: {filetype}")

        # ====================================================
        # 4. Find resumable jobs
        # ====================================================

        job_id = None

        if args.mode in {"resume", "resumebatch"}:

            print()
            print(
                "Looking for resumable "
                "translation jobs..."
            )

            resumable_jobs = find_resumable_jobs(
                args.input,
                args.from_lang,
                args.to_lang,
                args.model,
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
                    state,
                ) in enumerate(
                    resumable_jobs,
                    1,
                ):

                    completed = state.get(
                        "chunks_completed",
                        len(
                            state.get(
                                "translations",
                                {}
                            )
                        ),
                    )

                    total = state.get(
                        "chunks_total",
                        0,
                    )

                    last_updated = state.get(
                        "last_updated",
                        "Unknown",
                    )

                    print(
                        f"{i}. Job from {timestamp}"
                    )

                    print(
                        f"   Job ID: "
                        f"{resumable_job_id}"
                    )

                    print(
                        f"   Progress: "
                        f"{completed}/"
                        f"{total} chunks"
                    )

                    print(
                        f"   Last updated: "
                        f"{last_updated}"
                    )

                # ------------------------------------------------
                # Ask user which job to resume
                # ------------------------------------------------

                while True:

                    choice = input(
                        "\nEnter job number to resume "
                        "(or 'n' for new job, "
                        "'q' to quit): "
                    ).strip()

                    # ------------------------------------------------
                    # New job
                    # ------------------------------------------------

                    if choice.lower() == "n":

                        job_id = None
                        break

                    # ------------------------------------------------
                    # Quit
                    # ------------------------------------------------

                    if choice.lower() == "q":

                        print("Aborting.")
                        sys.exit(0)

                    # ------------------------------------------------
                    # Job number
                    # ------------------------------------------------

                    try:

                        index = int(choice) - 1

                        if 0 <= index < len(
                            resumable_jobs
                        ):

                            job_id = (
                                resumable_jobs[index][0]
                            )

                            break

                    except ValueError:
                        pass

                    print(
                        "Invalid choice. "
                        "Please try again."
                    )

            else:

                print()
                print("No resumable jobs found.")

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
            {},
        )

        api_key = openai_config.get(
            "api_key"
        )

        base_url = openai_config.get(
            "base_url"
        )

        # ====================================================
        # Validate API key
        # ====================================================

        if not api_key:

            print()
            print("=" * 60)
            print("ERROR")
            print("=" * 60)

            print(
                "API key is not configured."
            )

            print()
            print(
                "Please check config.yaml:"
            )

            print()
            print("openai:")
            print("  api_key: YOUR_API_KEY")

            print("=" * 60)

            sys.exit(1)

        # ====================================================
        # Validate base URL
        # ====================================================

        if not base_url:

            print()
            print("=" * 60)
            print("ERROR")
            print("=" * 60)

            print(
                "API base URL is not configured."
            )

            print()
            print(
                "Please check config.yaml:"
            )

            print()
            print("openai:")
            print(
                "  base_url: "
                "https://api.gapgpt.app/v1"
            )

            print("=" * 60)

            sys.exit(1)

        # ====================================================
        # 6. Create API client
        # ====================================================

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        print()
        print("API client initialized.")
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

            # ------------------------------------------------
            # User provided an existing directory
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Create parent directory
            # ------------------------------------------------

            output_path_obj.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_path = str(
                output_path_obj
            )

        else:

            # ------------------------------------------------
            # Default output directory
            # ------------------------------------------------

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
        # 8. Get translation prompt
        # ====================================================

        print()
        print("=" * 60)
        print("Translation Prompt")
        print("=" * 60)

        translation_prompt = (
            get_translation_prompt(
                from_lang=args.from_lang,
                to_lang=args.to_lang,
                filetype=filetype,
            )
        )

        # ====================================================
        # 8b. Additional output formats
        # ====================================================

        output_formats = None

        if args.outputs:

            try:

                if str(args.outputs).strip().lower() == "all":

                    output_formats = (
                        available_output_formats()
                    )

                else:

                    output_formats = normalize_outputs(
                        args.outputs
                    )

            except ValueError as error:

                print()
                print("ERROR")
                print("-" * 60)
                print(str(error))
                print("-" * 60)

                sys.exit(1)

        # ====================================================
        # SRT subtitles use a dedicated subtitle pipeline
        # ====================================================

        if filetype == "srt":

            from app.output.srt import translate_srt

            print()
            print("=" * 60)
            print("Starting SRT translation...")
            print("=" * 60)

            translate_srt(
                client,
                input_path,
                output_path,
                from_lang=args.from_lang,
                to_lang=args.to_lang,
                model=args.model,
                mode=args.mode or "fast",
                translation_prompt=translation_prompt,
                debug=args.debug,
            )

            print()
            print("=" * 60)
            print("SRT translation completed.")
            print("=" * 60)

            return

        # ====================================================
        # 9. Start translation
        # ====================================================
        # ====================================================

        print()
        print("=" * 60)
        print("Starting translation...")
        print("=" * 60)
        print()

        translate(
            client,
            args.input,
            output_path,
            args.from_lang,
            args.to_lang,
            mode=args.mode,
            model=args.model,

            # Fast mode is enabled unless
            # the user explicitly selected a batch mode.
            fast=(
                args.mode
                not in {
                    "batch",
                    "batchcheck",
                    "resumebatch",
                }
            ),

            resume_job_id=job_id,

            debug=args.debug,

            filetype=filetype,

            # ------------------------------------------------
            # User's translation prompt
            # ------------------------------------------------

            translation_prompt=translation_prompt,

            output_formats=output_formats,
            style_preset=args.style,
        )

        # ====================================================
        # 10. Finished
        # ====================================================

        print()
        print("=" * 60)
        print("Translation process finished.")
        print("=" * 60)

    # ========================================================
    # USER INTERRUPT
    # ========================================================

    except KeyboardInterrupt:

        print()
        print("=" * 60)
        print("TRANSLATION INTERRUPTED")
        print("=" * 60)

        print(
            "The translation was interrupted "
            "by the user."
        )

        print(
            "Completed translations were saved."
        )

        print(
            "Run again with "
            "--mode resume "
            "to continue."
        )

        print("=" * 60)

        sys.exit(130)

    # ========================================================
    # APPLICATION ERROR
    # ========================================================

    except Exception as e:

        error_text = str(e)

        # ====================================================
        # API QUOTA ERROR
        # ====================================================

        if (
            "insufficient_user_quota"
            in error_text
            or "pre-consume quota failed"
            in error_text
        ):

            print()
            print("=" * 60)
            print("QUOTA EXHAUSTED")
            print("=" * 60)

            print(
                "API quota is not sufficient "
                "for the next request."
            )

            print(
                "Your translation progress "
                "has been saved."
            )

            print(
                "Add API credit and run again "
                "with:"
            )

            print()

            print(
                'python -m app.main '
                '--input "C:\\path\\to\\book.epub" '
                '--from EN '
                '--to FA '
                '--model gpt-5.6-luna '
                '--mode resume'
            )

            print("=" * 60)

            sys.exit(2)

        # ====================================================
        # GENERAL APPLICATION ERROR
        # ====================================================

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
# PYTHON APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()