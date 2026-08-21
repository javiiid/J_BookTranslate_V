import sys

from app.jobs.state import find_resumable_jobs

def select_resumable_job(input_epub_path, from_lang, to_lang, model, mode):
    """Helper function to select a resumable job, used by both resume and resumebatch modes"""
    print("\nLooking for resumable translation jobs... [select_resumable_job]")
    resumable_jobs = find_resumable_jobs(input_epub_path, from_lang, to_lang, model)
    if not resumable_jobs:
        print("\nNo resumable jobs found. [select_resumable_job]")
        if mode == 'resumebatch':
            print("Please run with --mode batch first to create a new batch job. [select_resumable_job]")
            sys.exit(1)
        choice = input("Start new translation job? (y/N): [select_resumable_job]")
        if choice.lower() != 'y':
            print("Aborting. [select_resumable_job]")
            return None
        return None
        
    print("\nFound resumable translation jobs: [select_resumable_job]")
    for i, (job_id, timestamp, state) in enumerate(resumable_jobs, 1):
        print(f"{i}. Job from {timestamp} [select_resumable_job]")
        print(f"   Progress: {state['chunks_completed']}/{state['chunks_total']} chunks [select_resumable_job]")
        print(f"   Last updated: {state['last_updated']} [select_resumable_job]")
    
    while True:
        choice = input("\nEnter job number to resume (or 'q' to quit): [select_resumable_job]")
        if choice.lower() == 'q':
            print("Aborting. [select_resumable_job]")
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(resumable_jobs):
                return resumable_jobs[idx][0]
        except ValueError:
            pass
        print("Invalid choice, please try again [select_resumable_job]")

