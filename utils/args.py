import argparse
import os
from urllib.parse import urlparse

def validate_log_level(value: str) -> str:
    levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if value.upper() in levels:
        return value.upper()
    else:
        raise argparse.ArgumentTypeError(f"Invalid log level: {value}")

def validate_rpc_url(value: str) -> str:
    """Ensure the RPC is a valid http/https URL."""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise argparse.ArgumentTypeError("RPC URL must start with http:// or https://")
    if not parsed.netloc:
        raise argparse.ArgumentTypeError("RPC URL missing hostname")
    return value


def validate_bin_path(value: str) -> str:
    """Ensure Sui binary path exists and is executable."""
    if not os.path.isfile(value):
        raise argparse.ArgumentTypeError(f"Binary not found: {value}")
    if not os.access(value, os.X_OK):
        raise argparse.ArgumentTypeError(f"Binary is not executable: {value}")
    return value

def parse_args():
    parser = argparse.ArgumentParser(
        description="Global arguments for the application",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--log-lvl",
        default="INFO",
        type=validate_log_level,
        help="Set the logging level [DEBUG, INFO, WARNING, ERROR]",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        help="Path to the log file. If not provided, logs will not be stored",
        required=False,
    )
    parser.add_argument(
        "--sui-gas-budget",
        type=int,
        help="Gas budget for the transaction",
        default=50000000,
    )
    parser.add_argument(
        "--sui-rpc",
        type=str,
        help="RPC server http/s",
        default="https://fullnode.mainnet.sui.io:443"
    )
    parser.add_argument(
        "--sui-bin-path",
        type=str,
        help="Sui binary path",
        default="/usr/local/bin/sui",
    )
    parser.add_argument(
        "--sui-ref-token-price",
        type=int,
        help="Sui reference token price in $",
        default=1,
        dest="sui_ref_token_price"
    )
    parser.add_argument(
        "--sui-ref-gas-price",
        type=int,
        help="Sui reference gas price in mist",
        default=1000,
        dest="sui_ref_gas_price"
        
    )

    args = parser.parse_args()
    return args

args = parse_args()