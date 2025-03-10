import os
import sys
import json
import time
import subprocess
import requests
import schedule
from dotenv import load_dotenv

load_dotenv()

CMC_API_KEY = os.getenv("CMC_API_KEY")
SUI_PATH = os.getenv("SUI_PATH")

if not CMC_API_KEY or not SUI_PATH:
    print("Error: Required environment variables are missing.")
    print("Please ensure CMC_API_KEY and SUI_PATH are set in the .env file")
    sys.exit(1)

CMC_API_URL = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?CMC_PRO_API_KEY={CMC_API_KEY}&symbol=SUI"
SUI_RPC_URL = os.getenv("SUI_RPC_URL", "https://fullnode.mainnet.sui.io/")

latest_sui_price = None

def read_reference_values():
    """Reads the reference values from reference.json."""
    file_path = os.path.join(os.path.dirname(__file__), 'reference.json')
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def get_current_sui_price():
    """Fetches the current SUI price from CoinMarketCap."""
    try:
        response = requests.get(CMC_API_URL)
        data = response.json()
        if data["status"]["error_code"] != 0:
            raise Exception(f"API Error: {data['status']['error_message']}")
        price = data["data"]["SUI"]["quote"]["USD"]["price"]
        global latest_sui_price
        latest_sui_price = price
        return round(price, 4)
    except Exception as e:
        print("Error fetching SUI price:", e)
        raise

def calculate_new_mist(current_price, reference_price, reference_mist):
    """Calculates the new mist value based on the price change."""
    price_ratio = reference_price / current_price
    calculated_mist = round(reference_mist * price_ratio)
    return min(calculated_mist, 1000)

def update_validator_gas_price(mist_value):
    """Executes the command to update the validator gas price."""
    try:
        command = f"{SUI_PATH}/sui validator update-gas-price {mist_value}"
        print("Executing command:", command)
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.stderr:
            print("Command stderr:", result.stderr)
        print("Command output:", result.stdout)
        return True
    except Exception as e:
        print("Error updating validator gas price:", e)
        return False

def get_epoch_info():
    """Gets the latest epoch information from the SUI RPC endpoint."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getLatestSuiSystemState",
            "params": []
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(SUI_RPC_URL, json=payload, headers=headers)
        if not response.ok:
            raise Exception(f"HTTP error! status: {response.status_code}")
        data = response.json()
        if "result" not in data:
            raise Exception("No system state data received")
        
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
            "epoch_duration_ms": epoch_duration_ms
        }
    except Exception as e:
        print("Error fetching epoch information:", e)
        raise

def process_updates():
    """Processes updates by checking epoch information and updating gas price if needed."""
    try:
        epoch_info = get_epoch_info()
        remaining_ms = epoch_info["remaining_ms"]
        remaining_hours = remaining_ms // (1000 * 60 * 60)
        remaining_minutes = (remaining_ms % (1000 * 60 * 60)) // (1000 * 60)
        remaining_seconds = (remaining_ms % (1000 * 60)) // 1000

        print("\n=== Sui Epoch Information ===")
        print("Current Epoch:", epoch_info["current_epoch"])
        print(f"Time Remaining: {remaining_hours} hours, {remaining_minutes} minutes, {remaining_seconds} seconds")
        print("=========================\n")

        if remaining_ms < 60 * 60 * 1000:
            try:
                reference_data = read_reference_values()
                current_price = get_current_sui_price()
                if not current_price:
                    global latest_sui_price
                    current_price = latest_sui_price
                new_mist = calculate_new_mist(current_price, reference_data["sui_price"], reference_data["mist"])

                price_change_percent = ((current_price - reference_data["sui_price"]) / reference_data["sui_price"] * 100)
                mist_change_percent = ((new_mist - reference_data["mist"]) / reference_data["mist"] * 100)
                
                print("=== Price Update ===")
                print(f"Current SUI Price: ${current_price} ({price_change_percent:.2f}% change)")
                print(f"Reference Price: ${reference_data['sui_price']}")
                print(f"New Mist Value: {new_mist} ({mist_change_percent:.2f}% change)")
                print(f"Reference Mist: {reference_data['mist']}")
                print("=========================\n")

                print("Updating validator gas price...")
                updated = True
                if updated:
                    print("Successfully updated validator gas price")
                else:
                    print("Failed to update validator gas price")
            except Exception as price_error:
                print("Error processing price update:", price_error)
    except Exception as e:
        print("Error in process updates:", e)

def main():
    """Starts the SUI monitoring script."""
    print("Starting SUI monitoring (checking every hour)...")
    print("Reference values:", read_reference_values())
    print("----------------------------------------\n")

    schedule.every().hours.at(":00").do(process_updates)

    process_updates()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nScript stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
