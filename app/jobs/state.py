import json
import os
from pathlib import Path
from datetime import datetime, timezone

from app.core.paths import ensure_dir, ensure_temp_structure


def save_job_state(paths, chunks_total, chunks_completed, translations):
    """Save current job state and translations"""
    state = {
        'chunks_total': chunks_total,
        'chunks_completed': chunks_completed,
        'last_updated': datetime.now(UTC).isoformat()
    }
    
    try:
        # Save state with fsync for durability
        with open(paths['state_file'], 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Save translations separately with fsync
        with open(paths['translations_file'], 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            
    except Exception as e:
        print(f"Warning: Could not save state: {e} [save_job_state]")
        # Continue processing but warn user
        print("Warning: Progress may not be resumable if the script is interrupted [save_job_state]")

def load_job_state(paths):
    """Load existing state and translations, making job_state.json optional"""
    state = {}
    try:
        # Load chunks.json (required)
        print(f"Loading chunks from: {paths['chunks_file']} [load_job_state]")
        if not paths['chunks_file'].exists():
            print(f"No chunks file found at: {paths['chunks_file']} [load_job_state]")
            return None
            
        with open(paths['chunks_file'], 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
            # Explicitly reconstruct chunks as list of tuples (id, text)
            state['chunks'] = [(id, text) for id, text in chunks_data['chunks']]
            # Properly reconstruct chapter_map from the stored format
            state['chapter_map'] = {
                chunk_id: (data['item'], data['pos']) 
                for chunk_id, data in chunks_data['chapter_map'].items()
            }

        # Add total chunks count
        state['chunks_total'] = len(state['chunks'])
            
        # Load translations.json (optional)
        print(f"Loading translations from: {paths['translations_file']} [load_job_state]")
        if paths['translations_file'].exists():
            with open(paths['translations_file'], 'r', encoding='utf-8') as f:
                state['translations'] = json.load(f)
                state['chunks_completed'] = len(state['translations'])
        else:
            state['translations'] = {}
            state['chunks_completed'] = 0

        # Extract timestamp from job_id directory name if exists
        if paths['job_dir'].exists():
            timestamp = paths['job_dir'].name.split('_')[-1]
            state['last_updated'] = f"{timestamp[:8]}T{timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}.000000+00:00"
                
    except Exception as e:
        print(f"Warning: Could not load state files: {e} [load_job_state]")
        print(f"Attempted to load from paths: [load_job_state]")
        for key, path in paths.items():
            print(f"  {key}: {path} (exists: {path.exists()}) [load_job_state]")
        return None
        
    return state

def save_chunks(paths, all_chunks, chapter_map):
    """Save initial chunks and chapter mapping"""
    chunks_data = {
        'chunks': [(id, text) for id, text in all_chunks],
        'chapter_map': {id: {'item': str(item), 'pos': pos} for id, (item, pos) in chapter_map.items()}
    }
    with open(paths['chunks_file'], 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2)

def save_system_prompt(paths, prompt):
    """Save the system prompt used by this translation job."""

    with open(
        paths["system_prompt_file"],
        "w",
        encoding="utf-8",
    ) as f:
        f.write(prompt)

        f.flush()
        os.fsync(f.fileno())


def load_system_prompt(paths):
    """Load the system prompt stored for this job."""

    prompt_file = paths["system_prompt_file"]

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"System prompt file not found: {prompt_file}"
        )

    with open(
        prompt_file,
        "r",
        encoding="utf-8",
    ) as f:
        prompt = f.read().strip()

    if not prompt:
        raise ValueError(
            f"System prompt is empty: {prompt_file}"
        )

    return prompt

def save_translations(paths, translations):
    """Save translations to translations.json with fsync for durability."""
    # Ensure all keys in translations are strings
    translations = {str(k): v for k, v in translations.items()}
    with open(paths['translations_file'], 'w', encoding='utf-8') as f:
        json.dump(translations, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

def find_resumable_jobs(input_epub_path, from_lang, to_lang, model):
    """Find all resumable jobs for the given parameters without requiring job_state.json"""
    temp_dir = ensure_dir("temp")
    resumable_jobs = []
    
    # Look for job directories
    prefix = f"{Path(input_epub_path).stem}_{from_lang}_{to_lang}_{model}_"
    for job_dir in temp_dir.iterdir():
        if not job_dir.is_dir():
            continue
            
        try:
            # Check if this is a job directory for our input file
            if not job_dir.name.startswith(prefix):
                print(f"Skipping directory {job_dir.name}: doesn't match pattern {prefix}* [find_resumable_jobs]")
                continue

            paths = ensure_temp_structure(job_dir.name)
            
            # Only require chunks.json and optionally translations.json
            if not paths['chunks_file'].exists():
                print(f"Skipping directory {job_dir.name}: missing chunks.json [find_resumable_jobs]")
                continue
                
            # Count total chunks
            with open(paths['chunks_file'], 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
                chunks_total = len(chunks_data['chunks'])
            
            # Count completed translations
            chunks_completed = 0
            if paths['translations_file'].exists():
                with open(paths['translations_file'], 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    chunks_completed = len(translations)
            else:
                print(f"Note: Directory {job_dir.name} has no translations.json yet [find_resumable_jobs]")
            
            if chunks_completed >= chunks_total:
                print(f"Found completed job in {job_dir.name}: {chunks_completed}/{chunks_total} chunks [find_resumable_jobs]")
            else:
                print(f"Found resumable job in {job_dir.name}: {chunks_completed}/{chunks_total} chunks completed [find_resumable_jobs]")
            
            # Extract and properly format timestamp from directory name
            date_part = job_dir.name.split('_')[-2]  # Format: YYYYMMDD
            time_part = job_dir.name.split('_')[-1]  # Format: HHMMSS
            
            # Parse each component
            year = date_part[:4]
            month = date_part[4:6]
            day = date_part[6:8]
            hour = time_part[:2]
            minute = time_part[2:4]
            second = time_part[4:6]
            
            raw_timestamp = f"{date_part}_{time_part}"
            padded_timestamp = f"{year}-{month}-{day}T{hour}:{minute}:{second}.000000+00:00"
            
            state = {
                'chunks_total': chunks_total,
                'chunks_completed': chunks_completed,
                'last_updated': padded_timestamp
            }
                
            resumable_jobs.append((job_dir.name, raw_timestamp, state))
                
        except Exception as e:
            print(f"Warning: Could not process directory {job_dir.name}: {e} [find_resumable_jobs]")
            continue
    
    return sorted(resumable_jobs, key=lambda x: x[2]['last_updated'], reverse=True)

