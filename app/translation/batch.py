import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from app.core.paths import ensure_dir

UTC = timezone.utc

from app.jobs.state import save_translations
from app.translation.prompts import get_translation_prompt
from app.translation.prompts import get_default_prompt
from app.glossary.service import load_snapshot, glossary_prompt


def save_batch_state(temp_dir, batch_id, input_file_id, timestamp, job_metadata, paths):
    """Save batch processing state for later checking"""
    state_file = temp_dir / f"batch_status_{timestamp}.json"
    state = {
        "batch_id": batch_id,
        "input_file_id": input_file_id,
        "timestamp": timestamp,
        "job_metadata": job_metadata,
        "paths": {k: str(v) for k, v in paths.items()}
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    return state_file


def load_batch_state(temp_dir):
    """Load most recent batch state file"""
    state_files = list(temp_dir.glob("batch_status_*.json"))
    if not state_files:
        return None
    latest_file = max(state_files, key=lambda f: f.stat().st_mtime)
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f), latest_file

def batch_translate_chunks(client, chunks, from_lang, to_lang, mode=None, model=None, 
                         test_translations=None, keep_temp=False, paths=None, chapter_map=None, filetype='epub'):
    """Handle translation of all chunks in a single batch"""
    # The signature used to default to 'gpt-5.6-terra', so a caller that
    # omitted `model` sent terra regardless of the configured default.
    if model is None:
        from app.core.models import resolve_default_model
        model = resolve_default_model()
    if mode == 'batchcheck':
        return {}, None, None

    # Extract input_epub_path from the job directory name
    if paths:
        input_epub_path = paths['job_dir'].parent.parent / paths['job_dir'].name.split('_')[0]
    else:
        input_epub_path = "unknown_input"  # Fallback value if paths not provided

    temp_dir = ensure_dir("temp")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    import select
    import sys
    
    # Create batch input file
    batch_file_path = temp_dir / f"batch_input_{timestamp}.jsonl"
    with open(batch_file_path, "w", encoding="utf-8") as f:
        for chunk_id, chunk_text in chunks:
            request = {
                "custom_id": chunk_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": glossary_prompt(get_default_prompt(from_lang, to_lang, filetype), chunk_text, load_snapshot(paths) if paths else {})
                        },
                        {
                            "role": "user",
                            "content": chunk_text
                        }
                    ],
                    "temperature": 0.2
                }
            }
            f.write(json.dumps(request) + "\n")
        
    # Process batch
    print("Uploading batch file... [batch_translate_chunks]")
    batch_file = client.files.create(
        file=open(batch_file_path, "rb"),
        purpose="batch"
    )
    input_file_id = batch_file.id
    
    # Delete batch input file after uploading, unless debug flag is set
    if not keep_temp:
        try:
            batch_file_path.unlink()
            print(f"Deleted batch input file: {batch_file_path} [batch_translate_chunks]")
        except Exception as e:
            print(f"Warning: Could not delete batch input file {batch_file_path}: {e} [batch_translate_chunks]")
    
    print(f"Creating batch job with file ID: {input_file_id} [batch_translate_chunks]")
    batch_job = client.batches.create(
        input_file_id=input_file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    
    batch_id = batch_job.id
    print(f"Batch job created with ID: {batch_id} [batch_translate_chunks]")
        
    print("\nBatch processing started. Checking initial status in 5 seconds... [batch_translate_chunks]")
    time.sleep(5)
    
    status = client.batches.retrieve(batch_id)
    print(f"Status: {status.status} - Completed: {status.request_counts.completed}/{status.request_counts.total} [batch_translate_chunks]")
    
    if status.status == "failed":
        print("Batch processing failed. [batch_translate_chunks]")
        return {}, input_file_id, status
        
    # Save state and exit if not failed
    job_metadata = {
        "input_file": str(input_epub_path),
        "from_lang": from_lang,
        "to_lang": to_lang,
        "model": model,
        "chapter_map": {chunk_id: {"item": str(item), "pos": pos} 
                       for chunk_id, (item, pos) in chapter_map.items()} if chapter_map else {}
    }
    
    state_file = save_batch_state(temp_dir, batch_id, input_file_id, timestamp, job_metadata, paths)
    print(f"\nBatch processing in progress. Saved state to: {state_file} [batch_translate_chunks]")
    print("Run script again with --mode batchcheck to check status and retrieve results [batch_translate_chunks]")
    return {}, input_file_id, status

def parse_batch_response(response):
    """Parse batch response into translations dictionary"""
    translations = {}
    for line in response.splitlines():
        if not line.strip():
            continue
        result = json.loads(line)
        chunk_id = result['custom_id']
        if 'response' in result and 'body' in result['response']:
            if 'choices' in result['response']['body'] and result['response']['body']['choices']:
                translated_text = result['response']['body']['choices'][0]['message']['content']
                # Remove markdown code block markers if present
                translated_text = re.sub(r'^```[a-zA-Z]*\n', '', translated_text)
                translated_text = re.sub(r'```$', '', translated_text)
                translations[chunk_id] = translated_text
    return translations

def batch_translate_chunks(client, chunks, from_lang, to_lang, mode=None, model=None, 
                         test_translations=None, keep_temp=False, paths=None, chapter_map=None, filetype='epub'):
    """Handle translation of all chunks in a single batch"""
    # The signature used to default to 'gpt-5.6-terra', so a caller that
    # omitted `model` sent terra regardless of the configured default.
    if model is None:
        from app.core.models import resolve_default_model
        model = resolve_default_model()
    if mode == 'batchcheck':
        return {}, None, None

    # Extract input_epub_path from the job directory name
    if paths:
        input_epub_path = paths['job_dir'].parent.parent / paths['job_dir'].name.split('_')[0]
    else:
        input_epub_path = "unknown_input"  # Fallback value if paths not provided

    temp_dir = ensure_dir("temp")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    import select
    import sys
    
    # Create batch input file
    batch_file_path = temp_dir / f"batch_input_{timestamp}.jsonl"
    with open(batch_file_path, "w", encoding="utf-8") as f:
        for chunk_id, chunk_text in chunks:
            request = {
                "custom_id": chunk_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": glossary_prompt(get_default_prompt(from_lang, to_lang, filetype), chunk_text, load_snapshot(paths) if paths else {})
                        },
                        {
                            "role": "user",
                            "content": chunk_text
                        }
                    ],
                    "temperature": 0.2
                }
            }
            f.write(json.dumps(request) + "\n")
        
    # Process batch
    print("Uploading batch file... [batch_translate_chunks]")
    batch_file = client.files.create(
        file=open(batch_file_path, "rb"),
        purpose="batch"
    )
    input_file_id = batch_file.id
    
    # Delete batch input file after uploading, unless debug flag is set
    if not keep_temp:
        try:
            batch_file_path.unlink()
            print(f"Deleted batch input file: {batch_file_path} [batch_translate_chunks]")
        except Exception as e:
            print(f"Warning: Could not delete batch input file {batch_file_path}: {e} [batch_translate_chunks]")
    
    print(f"Creating batch job with file ID: {input_file_id} [batch_translate_chunks]")
    batch_job = client.batches.create(
        input_file_id=input_file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    
    batch_id = batch_job.id
    print(f"Batch job created with ID: {batch_id} [batch_translate_chunks]")
        
    print("\nBatch processing started. Checking initial status in 5 seconds... [batch_translate_chunks]")
    time.sleep(5)
    
    status = client.batches.retrieve(batch_id)
    print(f"Status: {status.status} - Completed: {status.request_counts.completed}/{status.request_counts.total} [batch_translate_chunks]")
    
    if status.status == "failed":
        print("Batch processing failed. [batch_translate_chunks]")
        return {}, input_file_id, status
        
    # Save state and exit if not failed
    job_metadata = {
        "input_file": str(input_epub_path),
        "from_lang": from_lang,
        "to_lang": to_lang,
        "model": model,
        "chapter_map": {chunk_id: {"item": str(item), "pos": pos} 
                       for chunk_id, (item, pos) in chapter_map.items()} if chapter_map else {}
    }
    
    state_file = save_batch_state(temp_dir, batch_id, input_file_id, timestamp, job_metadata, paths)
    print(f"\nBatch processing in progress. Saved state to: {state_file} [batch_translate_chunks]")
    print("Run script again with --mode batchcheck to check status and retrieve results [batch_translate_chunks]")
    return {}, input_file_id, status


def parse_batch_response(response):
    """Parse batch response into translations dictionary"""
    translations = {}
    for line in response.splitlines():
        if not line.strip():
            continue
        result = json.loads(line)
        chunk_id = result['custom_id']
        if 'response' in result and 'body' in result['response']:
            if 'choices' in result['response']['body'] and result['response']['body']['choices']:
                translated_text = result['response']['body']['choices'][0]['message']['content']
                # Remove markdown code block markers if present
                translated_text = re.sub(r'^```[a-zA-Z]*\n', '', translated_text)
                translated_text = re.sub(r'```$', '', translated_text)
                translations[chunk_id] = translated_text
    return translations

def check_batch_status(client, debug=False):
    """Check status of most recent batch job and return state if complete"""
    temp_dir = ensure_dir("temp")
    state_data = load_batch_state(temp_dir)
    
    if not state_data:
        print("No batch state found. Run with --mode batch first. [check_batch_status]")
        return None, None, None
    
    state, state_file = state_data
    
    batch_id = state['batch_id']
    print(f"Checking status for batch {batch_id} [check_batch_status]")
    status = client.batches.retrieve(batch_id)
    
    print(f"Status: {status.status} [check_batch_status]")
    print(f"Progress: {status.request_counts.completed}/{status.request_counts.total} [check_batch_status]")
    
    # Handle expired or cancelled batches with partial results
    if status.status in ['expired', 'cancelled', 'cancelling']:
        if status.request_counts.completed > 0:
            print(f"\nBatch {status.status} but has {status.request_counts.completed} completed requests [check_batch_status]")
            print("Attempting to save partial results... [check_batch_status]")
            
            translations = save_partial_batch_results(client, temp_dir, batch_id, state_file, status)
            if translations:
                print("\nPartial results saved successfully [check_batch_status]")
                print("You can now use --mode resume to complete the remaining translations [check_batch_status]")
        else:
            print(f"\nBatch {status.status} with 0 completed requests [check_batch_status]")
            
        # Only clean up batch state file if debug mode is not set
        if not debug:
            try:
                if state_file.exists():
                    state_file.unlink()
                    print(f"Cleaned up batch state file [check_batch_status]")
            except Exception as e:
                print(f"Warning: Could not remove batch state file: {e} [check_batch_status]")
        else:
            print("Debug mode: Preserving batch state file [check_batch_status]")
            
        return None, None, None
    
    if status.status != "completed":
        return None, None, None
    
    print("Batch completed! Will retrieve results... [check_batch_status]")
    response = client.files.content(status.output_file_id)
    response_text = response.read().decode('utf-8')
    return state, state_file, status

def save_partial_batch_results(client, temp_dir, batch_id, state_file_path, status):
    """Save partial results from an expired/cancelled batch job"""
    try:
        # First download the output file from the API
        if not status.output_file_id:
            print("No output file available [save_partial_batch_results]")
            return None
            
        print(f"Downloading output file {status.output_file_id}... [save_partial_batch_results]")
        response = client.files.content(status.output_file_id)
        output_text = response.read().decode('utf-8')
        
        # Save the raw output file
        output_filename = f"batch_{batch_id}_output.jsonl"
        output_path = temp_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Saved raw output to: {output_path} [save_partial_batch_results]")
            
        translations = {}
        # Process the downloaded content line by line
        for line in output_text.splitlines():
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                chunk_id = result.get('custom_id')
                if not chunk_id:
                    continue
                    
                response = result.get('response', {})
                if not response or response.get('error'):
                    continue
                    
                body = response.get('body', {})
                choices = body.get('choices', [])
                if not choices:
                    continue
                    
                content = choices[0].get('message', {}).get('content')
                if content:
                    translations[chunk_id] = content
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Warning: Error processing result for chunk {chunk_id}: {e} [save_partial_batch_results]")
                continue
        
        if not translations:
            print("No valid translations found in partial results [save_partial_batch_results]")
            return None
            
        print(f"Found {len(translations)} valid translations in partial results [save_partial_batch_results]")
        
        # Load the original job state to get the temp directory structure
        with open(state_file_path, 'r', encoding='utf-8') as f:
            original_state = json.load(f)
            
        # Reconstruct the paths dictionary
        paths = {k: Path(v) for k, v in original_state['paths'].items()}
        
        # Save the translations to the original job's translations file
        save_translations(paths, translations)
        print(f"Saved {len(translations)} translations to {paths['translations_file']} [save_partial_batch_results]")
        
        return translations
        
    except Exception as e:
        print(f"Error processing partial results: {e} [save_partial_batch_results]")
        return None

