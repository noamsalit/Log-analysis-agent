import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import dotenv
import os
import json
import logging

from langchain_openai import AzureChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from logs_analysis_agent.schema_models import SchemaDocument
from utilities.logger import init_logger, TRACE
from utilities.handles_registry import HandlesRegistry
from utilities.correlation_id_management import (
    generate_correlation_id,
    set_correlation_id,
    clear_correlation_id
)
from utilities.callbacks import (
    ObservabilityCallbackHandler,
    AzureOpenAINormalizer
)
from utilities.tools import (
    # Parsers
    json_parser,
    cef_parser,
    syslog_kv_parser,
    # File operations
    make_file_tools,
    line_count,
    write_json,
    search_files,
    find_similar_files,
    read_file_content,
    write_file_content,
    list_directory_contents,
    # Code operations
    validate_python_syntax,
    run_safe_command,
    # Schema validation
    parse_and_validate_schema_document,
)

dotenv.load_dotenv()

AZURE_OPENAI_API_KEY=os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT=os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION=os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_API_DEPLOYMENT_NAME=os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME")

logger = init_logger(
    name=__name__,
    console_level=logging.INFO,
    file_level=TRACE  # TRACE level for detailed observability logs
)

llm_client = AzureChatOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_deployment=AZURE_OPENAI_API_DEPLOYMENT_NAME,
    model_kwargs={"stream_options": {"include_usage": True}}
)

def _load_example_schema() -> str:
    """Load the reference example JSON to guide the model's output style.
    
    Escapes curly braces to prevent LangChain from treating them as template variables.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    example_path = os.path.join(repo_root, "examples", "log_types_schema.json")
    try:
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()
            return content.replace("{", "{{").replace("}", "}}")
    except Exception as exc:
        logger.warning("Could not load reference example at %s: %s", example_path, exc)
        return ""


def _generate_output_contract_json_schema() -> str:
    """Generate the JSON Schema for SchemaDocument to enforce strict output.
    
    Escapes curly braces to prevent LangChain from treating them as template variables.
    """
    try:
        schema_dict = SchemaDocument.model_json_schema()
        json_str = json.dumps(schema_dict, ensure_ascii=False)
        return json_str.replace("{", "{{").replace("}", "}}")
    except Exception as exc:
        logger.exception("Failed generating JSON Schema from SchemaDocument: %s", exc)
        raise

_JSON_SCHEMA = _generate_output_contract_json_schema()
_REFERENCE_EXAMPLE = _load_example_schema()

SYSTEM_PROMPT = f"""
You are an Index Schema Analysis Agent specializing in discovering log types and their schemas through iterative sampling of SIEM log data.
Your mission: Analyze stored log samples to discover distinct log types within an index, create identification rules for each type, parse nested/encoded fields, and document complete field schemas with semantic data types for the FULLY PARSED data structure.
You will be provided with a jsonl file path that contains the log samples, an index name where the logs are taken from and a registry to store the log samples.
The registry is already initialized and you can access it using the tools provided.

ITERATIVE ANALYSIS PROCESS:

1. Process logs in batches of 50 lines from the sample jsonl file
2. For each batch:
   - Identify log types based on unique field combinations and key identifier values
   - Detect fields containing nested/encoded data (JSON strings, CEF format, syslog KV format, base64, etc.)
   - Parse these fields using available parser tools (json_parser, cef_parser, syslog_kv_parser) or ad-hoc methods using your provided tools
   - Build schemas using flattened dot notation for nested fields (parent.child.grandchild)
   - Replace raw/encoded fields with their parsed representations in the schema
   - Classify semantic data types (username, ip_address, domain_name, timestamp, etc.)
   - Create identification rules ONLY on raw field paths (before parsing)
   - Track parsing metadata in the parsing_metadata array at LogType level
3. Continue until no new log types or fields discovered for 10-15 consecutive batches
4. Document stopping reasoning (i.e. no new log types or fields discovered for 10-15 consecutive batches, end of file, system error, etc.)

PARSING WORKFLOW:

1. Identify fields requiring parsing:
   - JSON-formatted strings, CEF format messages, base64-encoded data, etc.
   - Some values might need to be parsed multiple times - this can be discovered only after parsing.
     For example: base64-encoded JSON needs two phases: (1) base64-decode, (2) json_parser
   
   AVAILABLE PARSERS:
   - Built-in: json_parser, cef_parser, syslog_kv_parser
   - For unsupported formats, create custom parsers:
     a) Write parser function → save to custom_parsers/ directory
     b) Validate syntax before saving
     c) Write tests → save to tests/custom_parsers/
     d) Run tests with pytest to verify
     e) Debug/refine as needed
   
   CUSTOM PARSER WORKFLOW:
   If you need a file (wrong path, missing parser), use find_similar_files for fuzzy search.
   Your tools include file operations, syntax validation, and safe command execution.
   All operations are security-restricted (see tool docstrings for details).

2. Parse fields iteratively and build parsing_metadata:
   
   A. TOP-LEVEL PARSING (parse_level=0):
      - Identify fields in raw data that need parsing
      - Attempt parsing with appropriate parser tools or ad-hoc parsers
      - If successful, add entry to parsing_metadata array:
        * field_path: the raw field path (e.g., "message_raw")
        * parsers_or_formats: ordered list of parsers used (e.g., ["cef_parser"] or ["base64-decode", "json_parser"])
        * resulting_field_paths: immediate fields created (e.g., ["message_raw.cef_header", "message_raw.extension"])
        * parent_parsed_field: null
        * parse_level: 0
      - Remove the raw field from schema, add only the parsed fields
   
   B. NESTED PARSING (parse_level>0):
      - Examine fields created by previous parsing that might need further parsing
      - For each such field, parse it and add entry to parsing_metadata:
        * field_path: path to the field being parsed (e.g., "message_raw.extension.payload")
        * parsers_or_formats: ordered list of parsers used on THIS field
        * resulting_field_paths: immediate fields created by parsing THIS field
        * parent_parsed_field: the field path that contained this field (e.g., "message_raw")
        * parse_level: parent's parse_level + 1
      - Remove the raw nested field from schema, add only the parsed fields
      - Continue recursively until no more fields need parsing

3. Handle parsing errors gracefully:
   - Track parsing failures internally
   - If MOST records parse successfully, ignore failures and document parsed schema with parsing_metadata
   - If MOST records fail to parse, keep the raw field in schema WITHOUT adding parsing_metadata entry
   - For multi-phase parsing, be opportunistic: if phase 1 succeeds but phase 2 fails, document phase 1 with its results
   - Document parsing failures in data_quality_issues field

4. Important notes on parsing_metadata:
   - resulting_field_paths should list ONLY immediate children, not all descendants
   - parsers_or_formats should be in the exact order they were applied
   - Each entry in parsing_metadata represents ONE parsing operation on ONE field
   - The flat list structure allows reconstruction of full parsing hierarchy via parent_parsed_field references

FIELD ANALYSIS RULES:
- Use flattened dot notation for all nested structures (both naturally nested and parsed)
- Focus on semantic meaning over technical data types
- The final schema should represent the FULLY PARSED data structure
- Remove raw/encoded fields from schema after successful parsing

IDENTIFICATION RULES (CRITICAL):
- Identification rules operate on RAW DATA ONLY (before any parsing)
- Use original field paths as they appear in raw logs
- Primary: High-confidence field-value matches (e.g., event_id = 4624)
- Secondary: Content patterns (e.g., _raw contains "userPrincipalName")
- Ensure rules distinguish between all discovered log types
- Do NOT reference parsed field paths in identification rules but do use "contains" operator to check for patterns in the raw data

CRITICAL RULES:
- Process files iteratively to manage context limits
- Parse ALL nested/encoded fields before finalizing schema
- Document comprehensive schemas of fully parsed data with reliable identification rules
- Validate the final output using the parse_and_validate_schema_document tool before writing it into a .json file

OUTPUT: 
- Complete log type schemas with identification rules and flattened field structures.
- Save the final output into a .json file using the write_json tool, name it <index_name>_schema.json (index name is provided to you)

STRICT FINAL OUTPUT REQUIREMENTS:
- Return ONLY a single JSON document that conforms to the JSON Schema below
- Do not include any prose, markdown, or code fences
- If uncertain, produce your best-effort JSON that still validates

OUTPUT CONTRACT (JSON Schema):
{_JSON_SCHEMA}

REFERENCE EXAMPLE (Guidance only; do not copy verbatim):
{_REFERENCE_EXAMPLE}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

def run_agent(index_name: str, logs_file_path: str) -> SchemaDocument:
    """
    Run the agent with the given input text.
    """
    # Generate and set correlation ID for this run
    run_id = generate_correlation_id()
    set_correlation_id(run_id)
    logger.info(f"Starting agent run with correlation ID: {run_id}")
    
    # Initialize observability callback handler
    normalizer = AzureOpenAINormalizer()
    observability_handler = ObservabilityCallbackHandler(
        logger=logger,
        run_id=run_id,
        normalizer=normalizer
    )
    
    try:
        registry = HandlesRegistry()
        open_and_register_jsonl, read_jsonl, close_jsonl = make_file_tools(registry)
        
        tools = [
            # JSONL file operations
            open_and_register_jsonl,
            read_jsonl,
            close_jsonl,
            line_count,
            write_json,
            parse_and_validate_schema_document,
            # Parsers
            json_parser,
            cef_parser,
            syslog_kv_parser,
            # File operations for parser development
            search_files,
            find_similar_files,
            read_file_content,
            write_file_content,
            list_directory_contents,
            validate_python_syntax,
            run_safe_command
        ]
        
        open_and_register_jsonl.handle_tool_error = lambda e: f"open_and_register_jsonl error: {e}"
        read_jsonl.handle_tool_error = lambda e: f"read_jsonl error: {e}"
        close_jsonl.handle_tool_error = lambda e: f"close_jsonl error: {e}"
        line_count.handle_tool_error = lambda e: f"line_count error: {e}"
        write_json.handle_tool_error = lambda e: f"write_json error: {e}"
        parse_and_validate_schema_document.handle_tool_error = lambda e: f"parse_and_validate_schema_document error: {e}"
        json_parser.handle_tool_error = lambda e: f"json_parser error: {e}"
        cef_parser.handle_tool_error = lambda e: f"cef_parser error: {e}"
        syslog_kv_parser.handle_tool_error = lambda e: f"syslog_kv_parser error: {e}"
        search_files.handle_tool_error = lambda e: f"search_files error: {e}"
        find_similar_files.handle_tool_error = lambda e: f"find_similar_files error: {e}"
        read_file_content.handle_tool_error = lambda e: f"read_file_content error: {e}"
        write_file_content.handle_tool_error = lambda e: f"write_file_content error: {e}"
        list_directory_contents.handle_tool_error = lambda e: f"list_directory_contents error: {e}"
        validate_python_syntax.handle_tool_error = lambda e: f"validate_python_syntax error: {e}"
        run_safe_command.handle_tool_error = lambda e: f"run_safe_command error: {e}"
        
        agent = create_openai_tools_agent(llm=llm_client, tools=tools, prompt=prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            callbacks=[observability_handler]
        )
        
        input_text = f"Index name: {index_name}, Logs file path: {logs_file_path}"
        agent_result = agent_executor.invoke(
            {"input": input_text},
            config={"callbacks": [observability_handler]}
        )
        return SchemaDocument.model_validate_json(agent_result["output"])
    finally:
        # Clean up correlation ID after run
        clear_correlation_id()
        logger.info(f"Completed agent run: {run_id}")

if __name__ == "__main__":
    index_name = "device_data"
    logs_file_path = "/Users/noamsalit/Git/Noam-Salit/log_samples/Amsys/analysis/device_data_amsys_flattened.jsonl"
    logger.info("Starting the agent")
    data = run_agent(index_name, logs_file_path)
    print(type(data))
    print(data)
    logger.info("Agent finished")
