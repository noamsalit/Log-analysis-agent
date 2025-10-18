# Log Schema Analysis Agent

**Production-ready LangChain agent that automatically analyzes log formats from any platform and generates comprehensive data schemas for automated ETL onboarding.**

This tool solves the **onboarding phase** of ETL pipelines—discovering and documenting log schemas upfront. The generated schemas can be stored in a vector database, enabling a downstream real-time ETL agent to process logs with high accuracy by leveraging pre-discovered parsing rules and semantic understanding.

Built to explore and demonstrate production-grade AI agent development with comprehensive observability, testing, and extensibility.

---

## The Problem

ETL systems need to understand log schemas from diverse platforms—security logs, audit trails, application errors, system events, network traffic, and more. **Onboarding new log sources** requires manual schema extraction: time-consuming, error-prone, and doesn't scale.

While platforms tend to be relatively stable, onboarding new log sources, detecting schema drift, or discovering nested data structures requires expert analysis. Each log format may contain:
- Multiple nested or encoded fields (JSON strings, CEF format, base64-encoded data)
- Complex semantic types requiring domain knowledge
- Multiple log types within a single data stream
- Evolving schemas across different platform versions

**Traditional approaches:**
- Manual inspection and documentation (weeks of effort per source)
- Static parsers that break when formats change
- No semantic understanding of field meanings
- Poor handling of multi-format or nested structures

## The Solution

An AI-powered agent that automates the entire schema discovery process:

1. **Iterative sampling** - Processes logs in batches, discovering patterns incrementally
2. **Intelligent parsing** - Detects and parses nested/encoded fields (JSON, CEF, syslog KV, base64)
3. **Semantic classification** - Identifies field meanings (IP addresses, usernames, timestamps, etc.)
4. **Log type separation** - Distinguishes multiple log types within a single index
5. **Identification rules** - Creates rules to classify future logs by type
6. **Extensible parsers** - Automatically creates custom parsers for unknown formats

**Output:** Structured JSON schemas ready for downstream normalization engines.

### How It Fits Into ETL Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ ONBOARDING PHASE (This Tool)                                 │
│                                                              │
│  Raw Log Samples → Schema Analysis Agent → Structured Schema │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                   ┌─────────────────┐
                   │  Vector DB      │
                   │  (Schema Store) │
                   └────────┬────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ REAL-TIME PHASE (Separate Agent)                             │
│                                                              │
│  Live Logs → Lookup Schema → Parse → Normalize → Output      │
└──────────────────────────────────────────────────────────────┘
```

**Key benefit:** Separating onboarding from real-time processing enables:
- **High accuracy**: Real-time agent uses pre-discovered parsing rules
- **Performance**: No expensive schema discovery in the hot path
- **Scalability**: One-time onboarding cost per log source

---

## Key Features

### 🎯 Core Capabilities

- **Automatic log type discovery** - Identifies distinct log types based on semantic purpose
- **Multi-phase parsing** - Handles nested parsing (e.g., base64 → JSON → CEF)
- **Flattened dot notation** - Represents nested structures as `parent.child.grandchild`
- **Parsing metadata tracking** - Documents complete parsing workflows for reproducibility
- **Identification rules** - Creates field-based rules for log type classification
- **Data quality reporting** - Flags issues and estimates confidence

### 🏗️ Production Features

- **Comprehensive observability** - Token tracking, metrics, correlation IDs, structured logging
- **Multiple logging levels** - INFO (summaries), DEBUG (metrics), TRACE (full agent reasoning)
- **Error handling** - Graceful degradation, detailed error logging
- **Flexible CLI** - YAML config files or command-line args, batch processing
- **Extensible architecture** - Plugin-based parsers, custom tool support
- **Test coverage** - Unit and integration tests following TDD principles

### 🔧 Technical Highlights

- **LangChain agent framework** with OpenAI tools integration
- **Pydantic v2 models** for type safety and validation
- **Custom callback handlers** for comprehensive observability
- **Token cost tracking** (billable vs. successful estimates)
- **Correlation ID system** for distributed tracing
- **Safe sandboxed execution** for custom parser generation
- **Built-in parsers:** JSON, CEF (Common Event Format), Syslog key-value

---

## Quick Start

### Prerequisites

- Python 3.9+
- Azure OpenAI API access (or adapt for other providers)
- Environment variables configured (see [Configuration](#configuration))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/log-schema-agent.git
cd log-schema-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

### Run Your First Analysis

```bash
python run_schema_agent.py \
  --index "security_logs=examples/raw_logs_samples.jsonl" \
  --output-dir results/
```

**Expected output:**
- Schema file: `results/security_logs_schema.json`
- Logs: `logs/agent_runner.log`
- Console: Real-time progress and summary

### Example Output

The agent produces structured schemas like this:

```json
{
  "index_name": "security_logs",
  "log_types": {
    "azure_ad_signin": {
      "name": "Azure Active Directory Sign-in Logs",
      "identification_rules": {
        "primary": [
          {
            "field": "_sourcetype",
            "operator": "equals",
            "value": "azure:aad:signin",
            "confidence": 0.95
          }
        ]
      },
      "schema": {
        "userPrincipalName": {
          "field_path": "userPrincipalName",
          "semantic_type": "username",
          "examples": ["user@company.com"]
        },
        "location.ipAddress": {
          "field_path": "location.ipAddress",
          "semantic_type": "ip_address",
          "examples": ["192.168.1.100"]
        }
      },
      "parsing_metadata": [
        {
          "field_path": "location.geoCoordinates",
          "parsers_or_formats": ["json_parser"],
          "resulting_field_paths": ["location.geoCoordinates.latitude", "location.geoCoordinates.longitude"],
          "parse_level": 0
        }
      ]
    }
  }
}
```

See [`examples/log_types_schema.json`](examples/log_types_schema.json) for a complete example.

---

## Architecture Overview

### High-Level Design

```
┌─────────────────┐
│   CLI Runner    │  ← Entry point, config management
└────────┬────────┘
         │
┌────────▼────────┐
│  Agent Executor │  ← LangChain AgentExecutor
│  (LangChain)    │     - Manages agent loop
└────────┬────────┘     - Tool orchestration
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────────────┐
│ Tools │ │ Callback Handler│  ← Observability layer
└───┬───┘ └──┬──────────────┘     - Metrics collection
    │        │                     - Token tracking
    │        │                     - Correlation IDs
    │   ┌────▼────┐
    │   │ Logger  │
    │   └─────────┘
    │
    ├─ File Operations (read, write, search)
    ├─ Parsers (JSON, CEF, syslog KV)
    ├─ Schema Validation
    └─ Safe Command Execution
```

### Component Breakdown

**1. Agent Core** (`logs_analysis_agent/`)
- `agent.py` - Main agent logic with system prompt
- `schema_models.py` - Pydantic models for output validation

**2. Tools** (`utilities/tools/`)
- `file_ops.py` - JSONL reading, file search, directory listing
- `parsers.py` - Built-in parsers (JSON, CEF, syslog KV)
- `code_ops.py` - Parser development tools (syntax validation, safe execution)
- `schema_validation.py` - Output validation against Pydantic schema

**3. Observability** (`utilities/callbacks/`)
- `observability_handler.py` - Main callback handler for LangChain events
- `metrics_models.py` - Pydantic models for all metrics types
- `tokens_counter.py` - Token usage tracking and cost estimation
- `model_normalizers.py` - LLM response normalization

**4. Supporting Infrastructure** (`utilities/`)
- `logger.py` - Custom logging with TRACE level
- `correlation_id_management.py` - Context-based correlation IDs
- `handles_registry.py` - File handle lifecycle management
- `paths.py` - Safe path resolution

For detailed observability architecture, see [OBSERVABILITY_IMPLEMENTATION.md](OBSERVABILITY_IMPLEMENTATION.md).

---

## Usage Examples

### Basic Usage

```bash
# Single index
python run_schema_agent.py \
  --index "myindex=path/to/logs.jsonl" \
  --output-dir results/
```

### Batch Processing with YAML

Create `datasets.yaml`:
```yaml
- index_name: security_logs
  log_file: log_samples/security.jsonl

- index_name: audit_logs
  log_file: log_samples/audit.jsonl

- index_name: application_logs
  log_file: log_samples/app.jsonl
```

Run:
```bash
python run_schema_agent.py \
  --input-config datasets.yaml \
  --output-dir results/
```

### Development Mode (Verbose Logging)

```bash
python run_schema_agent.py \
  --index "myindex=logs.jsonl" \
  --output-dir results/ \
  --log-level TRACE \
  --console-level DEBUG
```

### Custom LLM Configuration

```bash
python run_schema_agent.py \
  --index "myindex=logs.jsonl" \
  --llm-model gpt-4-turbo \
  --llm-temperature 0.0 \
  --output-dir results/
```

For complete CLI documentation, see [CLI_USAGE.md](CLI_USAGE.md).

---

## Extensibility

### Custom Parsers

The agent can automatically create custom parsers for unknown log formats:

1. **Automatic detection** - Agent identifies unsupported formats during analysis
2. **Parser generation** - Writes parser function to `custom_parsers/`
3. **Test creation** - Generates tests in `tests/custom_parsers/`
4. **Validation** - Runs pytest to verify correctness
5. **Integration** - Uses parser immediately for remaining analysis

Custom parsers are sandboxed for security:
- Read access: entire repository
- Write access: only `custom_parsers/` and `tests/custom_parsers/`
- Execute access: whitelisted commands only (pytest, python, black, ruff)

See [custom_parsers/README.md](custom_parsers/README.md) for details.

### Built-in Parsers

Available parsers (in `utilities/tools/parsers.py`):
- **`json_parser`** - Parse JSON-formatted strings
- **`cef_parser`** - Parse Common Event Format (CEF) messages
- **`syslog_kv_parser`** - Parse syslog key-value pairs

### Adding New Tools

The agent can be extended with new tools by:
1. Creating a LangChain tool function with `@tool` decorator
2. Adding it to the tools list in `agent.py`
3. Documenting it in the tool's docstring (the agent reads these!)

---

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_API_DEPLOYMENT_NAME=gpt-4
```

### Logging Levels

The observability system supports three levels:

| Level | Agent Summary | LLM Metrics | Tool Args | Agent Reasoning |
|-------|--------------|-------------|-----------|-----------------|
| **INFO** | ✅ | Token summary only | ❌ | ❌ |
| **DEBUG** | ✅ | ✅ All metrics | Metadata only | ❌ |
| **TRACE** | ✅ | ✅ All metrics | ✅ Full args | ✅ Step-by-step |

**Recommendation:** Use `--log-level TRACE` for files, `--console-level INFO` for terminal.

---

## Project Structure

```
.
├── logs_analysis_agent/        # Core agent implementation
│   ├── agent.py                # Main agent logic
│   └── schema_models.py        # Pydantic output models
├── utilities/                  # Supporting infrastructure
│   ├── callbacks/              # Observability handlers
│   ├── tools/                  # Agent tools (parsers, file ops, etc.)
│   ├── logger.py               # Custom logging
│   ├── correlation_id_management.py
│   └── handles_registry.py
├── custom_parsers/             # Runtime-generated parsers
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── examples/                   # Example configs and outputs
├── log_samples/                # Sample log data
├── run_schema_agent.py         # CLI entry point
├── CLI_USAGE.md                # Complete CLI reference
├── OBSERVABILITY_IMPLEMENTATION.md  # Observability deep-dive
└── README.md                   # This file
```

---

## Testing

### Run All Tests

```bash
# Run full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=logs_analysis_agent --cov=utilities --cov-report=html

# Run specific test file
pytest tests/unit/utilities/test_callbacks.py -v
```

### Test Organization

Tests follow TDD principles with parametrized scenarios:
- **Success cases** - Happy path and basic variants
- **Edge cases** - Boundary conditions, empty inputs
- **Error cases** - Exceptions, invalid inputs

See [tests/custom_parsers/README.md](tests/custom_parsers/README.md) for testing guidelines.

---

## Documentation

This project includes comprehensive documentation for different audiences:

- **[CLI Usage Guide](CLI_USAGE.md)** - Complete CLI reference with examples and troubleshooting
- **[Observability Implementation](OBSERVABILITY_IMPLEMENTATION.md)** - Deep dive into metrics, logging, and monitoring architecture
- **[Custom Parsers Guide](custom_parsers/README.md)** - Developer guide for extending the agent with new log format parsers
- **[Testing Custom Parsers](tests/custom_parsers/README.md)** - Testing patterns and best practices

---

## Technical Implementation Notes

### Design Decisions

**Why LangChain?**
- Robust agent framework with tool orchestration
- Extensive callback system for observability
- Strong community and ecosystem

**Why iterative batch processing?**
- Manages token/context limits effectively
- Enables progressive discovery (stop when no new patterns found)
- Reduces cost by avoiding full file processing when unnecessary

**Why Pydantic for output?**
- Type safety and validation
- Self-documenting schemas (JSON Schema generation)
- Easy integration with downstream systems

**Why custom parsers?**
- Log formats are diverse and unpredictable
- Agent can handle unknown formats autonomously
- Tests ensure reliability of generated parsers

### Performance Considerations

- **Token usage:** ~3K-10K tokens per batch (50 logs)
- **Processing time:** ~30-60 seconds per batch
- **Stopping criteria:** No new discoveries for 10-15 batches
- **Cost estimation:** Tracked via `AgentTokenSummaryMetrics`

---

## Observability Features

### Metrics Collected

**LLM Metrics:**
- Model name/version, token usage (prompt, completion, total)
- Duration, success/failure status, error details

**Tool Metrics:**
- Tool name, input size, output size
- Duration, success/failure, error types

**Agent Metrics:**
- Run ID (correlation ID), start/end times
- Total duration, token summary (billable estimate)
- Input/output sizes

**Parsing Metrics:**
- Parser type, lines parsed, success rate
- Field discovery counts, validation errors

**Batch Metrics:**
- Batch number, lines processed (per batch + cumulative)
- New log types discovered, new fields discovered

### Correlation IDs

Every agent run gets a unique correlation ID (`run_<12-hex>`) that flows through all metrics, enabling:
- End-to-end request tracing
- Multi-component debugging
- Performance analysis across components

### Structured Logging

All metrics are logged as structured JSON with Pydantic models for:
- Type safety
- Easy parsing for downstream analytics
- Consistent schema across all events

---

## Future Enhancements

### Core Features
- [ ] Support for OpenAI, Anthropic, and other LLM providers
- [ ] Parallel processing of multiple indexes
- [ ] Incremental schema updates (delta detection)
- [ ] Schema comparison and drift detection
- [ ] Enhanced custom parser library with common formats
- [ ] Automatic normalization rule generation (next pipeline stage)

### Developer Experience
- [ ] Integration tests for end-to-end workflows
- [ ] Dockerize the agent for containerized deployment
- [ ] Enhanced YAML configuration to replace most CLI arguments (CLI overrides YAML)
- [ ] Web UI for schema visualization and interactive exploration

### Security & Production Readiness
- [ ] Agent privilege validation (refuse to run as root/privileged user)
- [ ] Callback handler redactor for sensitive data (PII, credentials)
- [ ] OpenTelemetry (OTel) integration for production observability
- [ ] Audit logging for compliance requirements

### Integration
- [ ] RESTful API for programmatic access
- [ ] Vector DB adapter for direct schema storage
- [ ] Real-time streaming log analysis hooks

---

## Learning Outcomes

This project was built to explore production-ready AI agent development. Key learnings:

### Agent Development
- **Prompt engineering** - Balancing instruction detail vs. token efficiency
- **Tool design** - Creating focused tools with clear interfaces
- **Iterative workflows** - Managing context windows in long-running tasks
- **Error recovery** - Graceful degradation and retry strategies

### Production Readiness
- **Observability** - Comprehensive metrics without overwhelming signal-to-noise
- **Token economics** - Tracking costs and optimizing for efficiency
- **Testing strategies** - Balancing coverage with maintenance burden
- **Documentation** - Writing for multiple audiences (users, developers, future self)

### LangChain Ecosystem
- **Callback handlers** - Deep integration for observability
- **Agent executor patterns** - When to use tools vs. direct LLM calls
- **Pydantic integration** - Type-safe inputs/outputs
- **Custom tool development** - Extending the framework

---

## Contributing

This is a personal learning/portfolio project, but suggestions and feedback are welcome!

If you find issues or have ideas:
1. Open an issue describing the problem or enhancement
2. For bugs, include logs (with sensitive data redacted)
3. For features, explain the use case and value

---

## License

MIT License - See LICENSE file for details

---

## Contact

**Noam Salit**
- GitHub: [@yourusername](https://github.com/yourusername)
- LinkedIn: [linkedin.com/in/yourprofile](https://linkedin.com/in/yourprofile)
- Email: your.email@example.com

---

## Acknowledgments

**Built with:**
- [LangChain](https://github.com/langchain-ai/langchain) - Agent framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) - LLM provider

**Developed using:**
- [Cursor IDE](https://cursor.sh/) - AI-powered code editor that significantly accelerated development

**Inspired by:** The challenges of building scalable ETL systems for diverse log sources.

---

**⭐ If you find this project interesting or helpful, please star the repository!**

