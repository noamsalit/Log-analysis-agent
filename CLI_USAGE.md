# Schema Analysis Agent - CLI Usage Guide

## Overview

The `run_schema_agent.py` script provides a command-line interface for running the schema analysis agent on multiple log datasets. It supports flexible configuration through both command-line arguments and YAML files.

## Quick Start

### Single Index

```bash
python run_schema_agent.py \
  --index "complete_endpoint=log_samples/Amsys/analysis/complete_endpoint_data_amsys_flattened.jsonl" \
  --output-dir results/
```

### Multiple Indexes

```bash
python run_schema_agent.py \
  --index "complete_endpoint=log_samples/Amsys/analysis/complete_endpoint_data_amsys_flattened.jsonl" \
  --index "network=log_samples/Amsys/analysis/network_data_amsys_flattened.jsonl" \
  --output-dir results/
```

### Using YAML Configuration

```bash
python run_schema_agent.py \
  --input-config examples/datasets_config.yaml \
  --output-dir results/
```

## Configuration Options

### Input Configuration

**Option 1: Command-line Arguments**
```bash
--index "index_name=path/to/logs.jsonl"  # Repeatable
```

**Option 2: YAML Configuration File**
```yaml
# datasets.yaml
- index_name: complete_endpoint
  log_file: log_samples/Amsys/analysis/complete_endpoint_data_amsys_flattened.jsonl

- index_name: network
  log_file: log_samples/Amsys/analysis/network_data_amsys_flattened.jsonl
```

Then use:
```bash
--input-config datasets.yaml
```

**Note:** You can combine both methods - indexes from both sources will be processed.

### LLM Configuration

By default, the CLI reads LLM credentials from your `.env` file. You can override any setting:

```bash
--llm-provider azure_openai           # Currently only Azure OpenAI is supported
--llm-api-key YOUR_API_KEY            # Override AZURE_OPENAI_API_KEY
--llm-endpoint https://your.endpoint  # Override AZURE_OPENAI_ENDPOINT
--llm-model your-deployment-name      # Override AZURE_OPENAI_API_DEPLOYMENT_NAME
--llm-api-version 2024-02-15-preview  # Override AZURE_OPENAI_API_VERSION
--llm-temperature 0.0                 # Default: 0.0 (deterministic)
```

### Output Configuration

```bash
--output-dir results/     # Required: Where to save schema files
--overwrite               # Optional: Overwrite existing schema files (default: skip)
```

Output files are named: `{index_name}_schema.json`

### Logging Configuration

```bash
--log-level DEBUG         # File log level: TRACE, DEBUG, INFO, WARNING, ERROR
--console-level INFO      # Console log level: TRACE, DEBUG, INFO, WARNING, ERROR
--log-file logs/run.log   # Log file path (default: logs/agent_runner.log)
```

**Recommended Settings:**
- Development: `--log-level TRACE --console-level DEBUG`
- Production: `--log-level DEBUG --console-level INFO`
- Quiet mode: `--log-level INFO --console-level WARNING`

### Execution Options

```bash
--stop-on-error    # Stop if any index fails (default: continue on error)
```

By default, the CLI will continue processing remaining indexes even if one fails. Use `--stop-on-error` to fail fast.

## Complete Examples

### Development: Verbose Logging

```bash
python run_schema_agent.py \
  --index "complete_endpoint=log_samples/Amsys/analysis/complete_endpoint_data_amsys_flattened.jsonl" \
  --output-dir results/ \
  --log-level TRACE \
  --console-level DEBUG \
  --overwrite
```

### Production: From Config, Continue on Error

```bash
python run_schema_agent.py \
  --input-config production_datasets.yaml \
  --output-dir /var/schemas/ \
  --log-level DEBUG \
  --console-level INFO \
  --log-file /var/log/schema_agent.log
```

### Custom LLM: Different Model

```bash
python run_schema_agent.py \
  --input-config datasets.yaml \
  --llm-model gpt-4-turbo \
  --llm-temperature 0.1 \
  --output-dir results/
```

### Mixed Input Sources

```bash
python run_schema_agent.py \
  --input-config datasets.yaml \
  --index "additional_index=path/to/additional.jsonl" \
  --output-dir results/
```

## Output Structure

The CLI creates:

1. **Schema files**: `{output_dir}/{index_name}_schema.json`
2. **Log file**: As specified by `--log-file` (default: `logs/agent_runner.log`)

### Schema File Format

Each schema file is a JSON document conforming to the `SchemaDocument` model:

```json
{
  "log_types": {
    "log_type_name": {
      "description": "...",
      "identification": {
        "rules": [...]
      },
      "fields": {
        "field_name": {
          "type": "...",
          "description": "..."
        }
      }
    }
  }
}
```

### Log Output

The CLI logs:
- Start/end of execution
- Configuration (non-sensitive only)
- Progress for each dataset
- Success/failure summary
- Any errors with full stack traces

**Example log output:**
```
2025-10-15 10:00:00,000 - INFO - ================================================================================
2025-10-15 10:00:00,001 - INFO - Schema Analysis Agent - CLI Runner
2025-10-15 10:00:00,002 - INFO - ================================================================================
2025-10-15 10:00:00,003 - INFO - LLM Provider: azure_openai
2025-10-15 10:00:00,004 - INFO - Output Directory: results/
2025-10-15 10:00:00,005 - INFO - Total datasets to process: 2
2025-10-15 10:00:00,006 - INFO -   - complete_endpoint: log_samples/Amsys/analysis/complete_endpoint_data_amsys_flattened.jsonl
2025-10-15 10:00:00,007 - INFO -   - network: log_samples/Amsys/analysis/network_data_amsys_flattened.jsonl
...
2025-10-15 10:05:30,123 - INFO - ================================================================================
2025-10-15 10:05:30,124 - INFO - Execution Summary
2025-10-15 10:05:30,125 - INFO - ================================================================================
2025-10-15 10:05:30,126 - INFO - Total: 2 datasets
2025-10-15 10:05:30,127 - INFO - Successful: 2
2025-10-15 10:05:30,128 - INFO - Failed: 0
2025-10-15 10:05:30,129 - INFO -   ✓ complete_endpoint
2025-10-15 10:05:30,130 - INFO -   ✓ network
```

## Error Handling

### Continue on Error (Default)

If one dataset fails, the CLI will:
1. Log the error with full stack trace
2. Mark that dataset as failed
3. Continue processing remaining datasets
4. Report summary at the end

### Stop on Error

With `--stop-on-error`, the CLI will:
1. Log the error
2. Stop immediately
3. Exit with non-zero code

### Exit Codes

- `0`: All datasets processed successfully
- `1`: One or more datasets failed

## Environment Variables

The CLI reads from `.env` by default:

```bash
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_API_DEPLOYMENT_NAME=gpt-4
```

CLI arguments override these environment variables.

## Troubleshooting

### "No module named 'yaml'"

Install PyYAML:
```bash
pip install pyyaml
```

### "Output file already exists"

Use `--overwrite` to force overwriting existing schema files.

### "Failed to load config file"

Ensure your YAML file:
- Is valid YAML syntax
- Contains a list of datasets
- Each dataset has both `index_name` and `log_file` keys

### High token usage / long runtime

Consider:
- Using a smaller log sample for testing
- Checking the agent logs for issues
- Using `--log-level TRACE` to see full LLM interactions

## Testing

Run the test suite:
```bash
python -m pytest tests/unit/test_run_schema_agent.py -v
```

## Future Enhancements

Planned features:
- Support for OpenAI, Anthropic, and other LLM providers
- Parallel processing of multiple indexes
- Dry-run mode for validation
- Progress bars and better terminal output
- Comparison reports between old and new schemas


