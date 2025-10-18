import argparse
import logging
import os
import sys

import config
import dotenv
import yaml

if str(config.PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(config.PROJECT_ROOT))

from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import AzureChatOpenAI

from logs_analysis_agent.agent import run_agent
from logs_analysis_agent.schema_models import SchemaDocument
from utilities.logger import LogLevel, init_logger

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


def create_llm_client(
    provider: str,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    model: Optional[str] = None,
    api_version: Optional[str] = None,
    temperature: Optional[float] = None
) -> Any:
    """
    Create an LLM client based on the specified provider and configuration.
    
    :param provider: LLM provider name (e.g., 'azure_openai')
    :param api_key: API key for authentication
    :param endpoint: API endpoint URL
    :param model: Model/deployment name
    :param api_version: API version (provider-specific)
    :param temperature: Sampling temperature (0.0 to 1.0). If None, uses model's default.
    :return: Configured LLM client instance
    """
    if provider == 'azure_openai':
        client_kwargs = {
            "api_key": api_key or os.getenv("AZURE_OPENAI_API_KEY"),
            "azure_endpoint": endpoint or os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_version": api_version or os.getenv("AZURE_OPENAI_API_VERSION"),
            "azure_deployment": model or os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME"),
            "model_kwargs": {"stream_options": {"include_usage": True}}
        }
        
        if temperature is not None:
            client_kwargs["temperature"] = temperature
        
        return AzureChatOpenAI(**client_kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def load_yaml_config(config_path: str) -> List[Dict[str, str]]:
    """
    Load log sample configuration from a YAML file.
    
    :param config_path: Path to YAML configuration file
    :return: List of dictionaries containing index_name and log_file keys
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if not isinstance(config, list):
        raise ValueError(f"YAML config must be a list of log samples, got: {type(config)}")
    
    for log_sample in config:
        if 'index_name' not in log_sample or 'log_file' not in log_sample:
            raise ValueError(
                f"Each log sample must have 'index_name' and 'log_file' keys. Got: {log_sample}"
            )
    
    return config


def parse_index_arg(index_str: str) -> Dict[str, str]:
    """
    Parse an --index argument in the format 'index_name=log_file_path'.
    
    :param index_str: Index argument string
    :return: Dictionary with index_name and log_file keys
    """
    if '=' not in index_str:
        raise ValueError(
            f"Invalid --index format: {index_str}. Expected format: index_name=log_file_path"
        )
    
    index_name, log_file = index_str.split('=', 1)
    return {'index_name': index_name.strip(), 'log_file': log_file.strip()}


def run_single_index(
    index_name: str,
    log_file: str,
    output_dir: Path,
    llm_client: Any,
    overwrite: bool
) -> bool:
    """
    Run the agent on a single index/dataset.
    
    :param index_name: Name of the log index
    :param log_file: Path to the log file
    :param output_dir: Directory to save output schema
    :param llm_client: Configured LLM client
    :param overwrite: Whether to overwrite existing output files
    :return: True if successful, False otherwise
    """
    output_file = output_dir / f"{index_name}_schema.json"
    
    if output_file.exists() and not overwrite:
        logger.warning(
            f"Output file already exists and --overwrite not set: {output_file}. Skipping."
        )
        return False

    try:
        result: SchemaDocument = run_agent(
            index_name=index_name,
            logs_file_path=log_file,
            llm_client=llm_client
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.model_dump_json(indent=2))
        
        log_types_count = len(result.log_types)
        logger.info(
            f"Successfully completed {index_name}: {log_types_count} log types discovered. "
            f"Output saved to: {output_file}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to process {index_name}: {e}", exc_info=True)
        return False


def parse_arguments():
    """
    Parse and validate command-line arguments.
    
    :return: Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Run schema analysis agent on log datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single index
  %(prog)s --index "complete_endpoint=logs/complete_endpoint.jsonl" --output-dir results/
  
  # Multiple indexes
  %(prog)s \\
    --index "complete_endpoint=logs/complete_endpoint.jsonl" \\
    --index "network=logs/network.jsonl" \\
    --output-dir results/
  
  # From YAML config
  %(prog)s --input-config datasets.yaml --output-dir results/
  
  # Custom LLM settings
  %(prog)s --input-config datasets.yaml \\
    --llm-api-key your-key \\
    --llm-model gpt-4 \\
    --output-dir results/
        """
    )
    
    input_group = parser.add_argument_group('input configuration')
    input_group.add_argument('--index', action='append', dest='indexes', metavar='INDEX_NAME=LOG_FILE', help='Index to process in format: index_name=log_file_path (repeatable). Overrides --input-config if both provided.')
    input_group.add_argument('--input-config', type=str, metavar='FILE', help='YAML file containing list of log samples with index_name and log_file keys. Ignored if --index is provided.')
    
    llm_group = parser.add_argument_group('LLM configuration')
    llm_group.add_argument('--llm-provider', type=str, default='azure_openai', choices=['azure_openai'], help='LLM provider (default: azure_openai, uses .env if not specified)')
    llm_group.add_argument('--llm-api-key', type=str, help='LLM API key (overrides environment variable)')
    llm_group.add_argument('--llm-endpoint', type=str, help='LLM endpoint URL (overrides environment variable)')
    llm_group.add_argument('--llm-model', type=str, help='LLM model/deployment name (overrides environment variable)')
    llm_group.add_argument('--llm-api-version', type=str, help='LLM API version (overrides environment variable)')
    llm_group.add_argument('--llm-temperature', type=float, default=None, help='LLM temperature (0.0-1.0). If not specified, uses model default.')
    
    output_group = parser.add_argument_group('output configuration')
    output_group.add_argument('--output-dir', type=str, required=True, help='Directory to save output schema files')
    output_group.add_argument('--overwrite', action='store_true', help='Overwrite existing output files (default: False)')
    
    log_group = parser.add_argument_group('logging configuration')
    log_group.add_argument('--log-level', type=str, default='DEBUG', choices=['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR'], help='File log level (default: DEBUG)')
    log_group.add_argument('--console-level', type=str, default='INFO', choices=['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Console log level (default: INFO)')
    log_group.add_argument('--log-file', type=str, default='logs/agent_runner.log', help='Path to log file (default: logs/agent_runner.log)')
    
    exec_group = parser.add_argument_group('execution options')
    exec_group.add_argument('--stop-on-error', action='store_true', help='Stop execution if any index fails (default: continue on error)')
    
    args = parser.parse_args()
    
    if not args.indexes and not args.input_config:
        parser.error("Either --index or --input-config must be provided")
    
    return args


def log_section_header(message: str) -> None:
    """
    Log a message with decorative borders.
    
    :param message: The message to log
    """
    logger.info("=" * 80)
    logger.info(message)
    logger.info("=" * 80)


def load_log_samples(args) -> List[Dict[str, str]]:
    """
    Load log samples from CLI arguments or YAML config.
    
    CLI arguments take precedence over YAML config file. If both are provided,
    only CLI arguments are used (YAML is ignored).
    
    :param args: Parsed command-line arguments
    :return: List of log sample dictionaries with 'index_name' and 'log_file' keys
    """
    if args.indexes:
        logger.info(f"Loading log samples from command-line arguments: {len(args.indexes)} indexes")
        if args.input_config:
            logger.warning(f"Note: --input-config ignored when --index is provided")
        try:
            logs_samples = []
            for index_str in args.indexes:
                logs_samples.append(parse_index_arg(index_str))
            return logs_samples
        except Exception as e:
            logger.error(f"Failed to parse --index argument: {e}")
            sys.exit(1)
    
    if args.input_config:
        logger.info(f"Loading log samples from config file: {args.input_config}")
        try:
            return load_yaml_config(args.input_config)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            sys.exit(1)
    
    logger.error("No log samples provided. Use --index or --input-config.")
    sys.exit(1)


def main(args):
    """
    Main execution logic for the CLI.
    
    :param args: Parsed command-line arguments
    :return: Exit code (0 for success, 1 for failure)
    """
    log_section_header("Schema Analysis Agent - CLI Runner")
    logger.info(f"LLM Provider: {args.llm_provider}")
    logger.info(f"Output Directory: {args.output_dir}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info(f"Console Level: {args.console_level}")
    logger.info(f"Continue on Error: {not args.stop_on_error}")
    logger.info(f"Overwrite: {args.overwrite}")
    
    logs_samples = load_log_samples(args)
    
    logger.info(f"Total log samples to process: {len(logs_samples)}")
    for log_sample in logs_samples:
        logger.info(f"  - {log_sample['index_name']}: {log_sample['log_file']}")
    

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory created/verified: {output_dir}")
    
    logger.info("Initializing LLM client...")
    try:
        llm_client = create_llm_client(
            provider=args.llm_provider,
            api_key=args.llm_api_key,
            endpoint=args.llm_endpoint,
            model=args.llm_model,
            api_version=args.llm_api_version,
            temperature=args.llm_temperature
        )
        logger.info("LLM client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        return 1
    
    log_section_header("Starting log sample processing")
    
    results = []
    for i, log_sample in enumerate(logs_samples, 1):
        logger.info(f"\nProcessing log sample {i}/{len(logs_samples)}: {log_sample['index_name']}")
        logger.info("-" * 80)
        
        success = run_single_index(
            index_name=log_sample['index_name'],
            log_file=log_sample['log_file'],
            output_dir=output_dir,
            llm_client=llm_client,
            overwrite=args.overwrite
        )
        
        results.append({
            'index_name': log_sample['index_name'],
            'success': success
        })
        
        if not success and args.stop_on_error:
            logger.error(f"Stopping execution due to failure in {log_sample['index_name']}")
            break
    
    log_section_header("Execution Summary")
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    logger.info(f"Total: {len(results)} log samples")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        logger.info(f"  {status} {result['index_name']}")
    
    if successful > 0:
        logger.info("")
        logger.info(f"Output files created in: {output_dir.absolute()}")
        logger.info("Generated schema files:")
        for result in results:
            if result['success']:
                output_file = output_dir / f"{result['index_name']}_schema.json"
                logger.info(f"  • {output_file.name}")
    
    log_section_header("Agent runner completed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    args = parse_arguments()
    log_file_path = Path(args.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    init_logger(
        name=__name__,
        console_level=LogLevel.from_string(args.console_level).value,
        file_level=LogLevel.from_string(args.log_level).value,
        log_dir=str(log_file_path.parent),
        log_file=log_file_path.name
    )
    
    sys.exit(main(args))
