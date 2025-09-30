import os
import sys
import time
import subprocess
import requests
from dotenv import load_dotenv

from utils.args import args
from utils.logger import logger

# Load environment variables
load_dotenv()

# CoinMarketCap API key
CMC_API_KEY = os.getenv("CMC_API_KEY")
if not CMC_API_KEY:
    logger.error("CMC_API_KEY is not set in the .env file")
    sys.exit(1)

# Global configuration
CMC_API_URL = (
    f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    f"?CMC_PRO_API_KEY={CMC_API_KEY}&symbol=SUI"
)
SUI_RPC_URL = args.sui_rpc
SUI_BIN_PATH = args.sui_bin_path
SUI_GAS_BUDGET = args.sui_gas_budget
SUI_REF_TOKEN_PRICE = args.sui_ref_token_price
SUI_REF_GAS_PRICE = args.sui_ref_gas_price
LAST_UPDATED_EPOCH = None

def get_current_sui_price():
    """Fetch the current SUI price from CoinMarketCap."""
    try:
        response = requests.get(CMC_API_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("status", {}).get("error_code") != 0:
            raise ValueError(f"CMC API Error: {data['status']['error_message']}")

        price = data["data"]["SUI"]["quote"]["USD"]["price"]

        return round(price, 4)

    except Exception as e:
        logger.error(f"Failed to fetch SUI price: {e}")
        raise

def get_epoch_info():
    """Get the latest epoch information from the SUI RPC endpoint."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getLatestSuiSystemState",
            "params": [],
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(SUI_RPC_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if "result" not in data:
            raise ValueError("No system state data received from RPC")

        system_state = data["result"]
        current_epoch = int(system_state["epoch"])
        epoch_start_timestamp_ms = int(system_state["epochStartTimestampMs"])
        epoch_duration_ms = int(system_state["epochDurationMs"])

        now = int(time.time() * 1000)
        epoch_end_timestamp = epoch_start_timestamp_ms + epoch_duration_ms
        remaining_ms = epoch_end_timestamp - now

        return {
            "current_epoch": current_epoch,
            "remaining_ms": remaining_ms,
            "epoch_end_timestamp": epoch_end_timestamp,
            "epoch_start_timestamp_ms": epoch_start_timestamp_ms,
            "epoch_duration_ms": epoch_duration_ms,
        }

    except Exception as e:
        logger.error(f"Failed to fetch epoch information: {e}")
        raise

def calculate_new_mist(current_price, reference_price, reference_mist):
    """Calculate the new mist value based on the price change."""
    price_ratio = reference_price / current_price
    calculated_mist = round(reference_mist * price_ratio)
    return min(calculated_mist, 1000)

def update_validator_gas_price(mist_value):
    """Execute the command to update the validator gas price."""
    try:
        command = (
            f"{SUI_BIN_PATH} validator update-gas-price {mist_value} "
            f"--gas-budget {SUI_GAS_BUDGET}"
        )
        logger.info(f"Executing: {command}")

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True
        )

        if result.stderr:
            logger.warning(f"Command stderr: {result.stderr.strip()}")
        if result.stdout:
            logger.debug(f"Command output: {result.stdout.strip()}")

        return result.returncode == 0

    except Exception as e:
        logger.error(f"Failed to update validator gas price: {e}")
        return False

def process_updates():
    """Check epoch information and update gas price if needed."""
    global LAST_UPDATED_EPOCH

    try:
        epoch_info = get_epoch_info()
        remaining_ms = epoch_info["remaining_ms"]
        current_epoch = epoch_info["current_epoch"]

        # Format remaining time
        remaining_hours = remaining_ms // (1000 * 60 * 60)
        remaining_minutes = (remaining_ms % (1000 * 60 * 60)) // (1000 * 60)
        remaining_seconds = (remaining_ms % (1000 * 60)) // 1000

        logger.info(
            f"Epoch {current_epoch} | "
            f"Time remaining: {remaining_hours}h {remaining_minutes}m {remaining_seconds}s"
        )

        # Skip if already updated this epoch
        if LAST_UPDATED_EPOCH == current_epoch:
            logger.info(f"Gas price already updated for epoch {current_epoch}, skipping.")
            return

        # Update gas price if less than 1 hour remains
        if remaining_ms < 60 * 60 * 1000:
            current_price = get_current_sui_price()

            logger.info(f"Fetched current $SUI price: ${current_price}")

            new_mist = calculate_new_mist(
                current_price, SUI_REF_TOKEN_PRICE, SUI_REF_GAS_PRICE
            )

            price_change_percent = (
                (current_price - SUI_REF_TOKEN_PRICE) / SUI_REF_TOKEN_PRICE * 100
            )
            mist_change_percent = (
                (new_mist - SUI_REF_GAS_PRICE) / SUI_REF_GAS_PRICE * 100
            )

            logger.info(
                f"SUI Price: ${current_price} ({price_change_percent:.2f}% vs ref ${SUI_REF_TOKEN_PRICE})"
            )
            logger.info(
                f"Mist Value: {new_mist} ({mist_change_percent:.2f}% vs ref {SUI_REF_GAS_PRICE})"
            )
            
            pass

            if update_validator_gas_price(new_mist):
                logger.info(f"Validator gas price updated successfully for epoch {current_epoch}")
                LAST_UPDATED_EPOCH = current_epoch
            else:
                logger.error(f"Validator gas price update failed for epoch {current_epoch}")

    except Exception as e:
        logger.error(f"Process update failed: {e}")

def main():
    """Start the SUI monitoring script loop."""
    logger.info("==============================================================")
    logger.info("Starting SUI Gas Price Monitor")
    logger.info(
        f"Reference values: SUI price=${SUI_REF_TOKEN_PRICE}, "
        f"GAS price={SUI_REF_GAS_PRICE} $MIST"
    )

    try:
        while True:
            try:
                process_updates()
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")

            logger.info("Sleeping for 10 minutes before next check...")
            time.sleep(10 * 60)
            logger.info("==============================================================")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()
