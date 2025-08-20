import os
import sys
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUTPUT_DIR, 'crew_kickoff.txt')
PROPOSAL_PATH = os.path.join(OUTPUT_DIR, 'crew_proposal.json')
CONTEXT_PATH = os.path.join(OUTPUT_DIR, 'crew_context_meta.json')


def write_log(lines):
    content = "\n".join(lines)
    with open(LOG_PATH, 'w') as f:
        f.write(content)
    print(content)


def main():
    load_dotenv()  # allow .env to set provider creds and model ids
    lines = []
    lines.append('CREW KICKOFF START')
    lines.append(f'Timestamp: {datetime.utcnow().isoformat()}Z')

    # Prepare Excel bytes
    excel_bytes = None
    excel_source = None

    # Preferred: use existing test Excel if available
    candidate = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_financial_data.xlsx'))
    if os.path.exists(candidate):
        try:
            with open(candidate, 'rb') as f:
                excel_bytes = f.read()
            excel_source = candidate
        except Exception as e:
            lines.append(f'Failed to read existing test Excel: {e}')

    if excel_bytes is None:
        lines.append('No test Excel found at Agent/test_data/dummy_financial_data.xlsx; cannot proceed with real Excel parsing.')
        lines.append('Please provide a valid .xlsx or adjust the path.')
        write_log(lines)
        return

    # Load config JSON from repository test data (no hardcoding)
    CONFIG_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_request.json'))
    if not os.path.exists(CONFIG_PATH):
        lines.append(f'Config JSON not found: {CONFIG_PATH}')
        write_log(lines)
        return
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
    except Exception as e:
        lines.append(f'Failed to read/parse config JSON: {e}')
        write_log(lines)
        return

    # Build context expected by crew/tasks/tools
    context = {
        "proposal_id": None,  # let server set in real endpoint; here we only run crew
        "config": config,
        "excel": {
            "filename": os.path.basename(excel_source),
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "bytes": excel_bytes,
        },
    }

    # Save meta context (without raw bytes) for audit
    meta = {
        "excel": {
            "filename": context["excel"]["filename"],
            "content_type": context["excel"]["content_type"],
            "size_bytes": len(excel_bytes),
        },
        "config_keys": list(config.keys()),
    }
    with open(CONTEXT_PATH, 'w') as f:
        json.dump(meta, f, indent=2)

    try:
        from crew import TreasuryCrew
        crew = TreasuryCrew()
        # Kick off proposal generation
        result = crew.generate_payment_proposal(context)

        # Try to coerce to JSON if string-like
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except Exception:
                parsed = {"raw": result}
            result = parsed

        with open(PROPOSAL_PATH, 'w') as f:
            json.dump(result, f, indent=2)

        lines.append('Crew kickoff: SUCCESS')
        lines.append(f'Proposal saved: {PROPOSAL_PATH}')
    except Exception:
        lines.append('Crew kickoff: FAILED')
        lines.append(traceback.format_exc())

    write_log(lines)


if __name__ == '__main__':
    main()
