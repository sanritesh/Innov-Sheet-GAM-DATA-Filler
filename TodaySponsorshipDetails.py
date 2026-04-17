import asyncio
import json
import sys
import os
from googleads import ad_manager
from datetime import datetime, timedelta

# Only import Quart if running as web server
if '--cli' not in sys.argv:
    try:
        from quart import Quart, jsonify
        app = Quart(__name__)
    except ImportError:
        app = None
else:
    app = None


def format_date_time(date_time):
    """Format Google Ad Manager DateTime object to ISO 8601 format."""
    if not date_time:
        return None
    try:
        dt = datetime(
            date_time['date']['year'],
            date_time['date']['month'],
            date_time['date']['day'],
            date_time['hour'],
            date_time['minute'],
            date_time['second']
        )
        return dt.isoformat()
    except Exception as e:
        return f"Error parsing dateTime: {str(e)}"

async def fetch_ad_unit_names_in_batches(client, ad_unit_ids):
    """Fetch Ad Unit names in batches."""
    batch_size = 50  # Adjust based on API limits or optimal batch size
    all_ad_units = {}
    
    # Split the AdUnit IDs into batches
    batched_ids = [ad_unit_ids[i:i + batch_size] for i in range(0, len(ad_unit_ids), batch_size)]

    # Function to fetch names for each batch
    async def fetch_batch(batch):
        ad_unit_service = client.GetService('InventoryService', version='v202602')
        statement = (ad_manager.StatementBuilder()
                     .Where('id IN ({})'.format(', '.join([str(aid) for aid in batch]))))

        try:
            response = ad_unit_service.getAdUnitsByStatement(statement.ToStatement())
            ad_units = {}
            if 'results' in response:
                for ad_unit in response['results']:
                    ad_units[ad_unit['id']] = ad_unit['name']
            return ad_units
        except Exception as e:
            return {"error": f"Error fetching Ad Unit names: {str(e)}"}

    # Process each batch asynchronously
    tasks = [fetch_batch(batch) for batch in batched_ids]
    batch_results = await asyncio.gather(*tasks)

    # Combine results from all batches
    for result in batch_results:
        if "error" not in result:
            all_ad_units.update(result)
        else:
            return result  # Return error if any batch fails

    return all_ad_units

def get_targeting_details(client, targeting, ad_unit_names_cache):
    targeting_details = {}

    try:
        if hasattr(targeting, 'inventoryTargeting') and targeting.inventoryTargeting:
            inventory_targeting = targeting.inventoryTargeting
            targeted_ad_units = []

            if hasattr(inventory_targeting, 'targetedAdUnits'):
                for ad_unit in inventory_targeting.targetedAdUnits:
                    ad_unit_id = ad_unit.adUnitId
                    ad_unit_name = ad_unit_names_cache.get(ad_unit_id, "Unknown")  # Use cached name
                    
                    targeted_ad_units.append({
                        "adUnitId": ad_unit_id,
                        "AdunitName": ad_unit_name,
                    })

            targeting_details['inventoryTargeting'] = targeted_ad_units
            
    
            
        
    except Exception as e:
        targeting_details['error'] = f"Error extracting targeting details: {str(e)}"

    return targeting_details


async def get_todays_sponsorships(client):
    """Fetch sponsorship line items scheduled to run today asynchronously."""
    line_item_service = client.GetService('LineItemService', version='v202602')
    today = datetime.now()
    start_time = today.strftime('%Y-%m-%dT00:00:00')
    end_time = today.strftime('%Y-%m-%dT23:59:59')

    statement = (
        ad_manager.StatementBuilder()
        .Where("lineItemType = 'SPONSORSHIP' AND startDateTime >= :start_time AND startDateTime < :end_time")
        .WithBindVariable('start_time', start_time)
        .WithBindVariable('end_time', end_time)
        .Limit(500)
    )

    response = line_item_service.getLineItemsByStatement(statement.ToStatement())

    results = []
    ad_unit_ids = set()

    # Collect all Ad Unit IDs before fetching names
    if 'results' in response:
        for line_item in response['results']:
            if hasattr(line_item, 'targeting') and line_item.targeting:
                if hasattr(line_item.targeting, 'inventoryTargeting'):
                    inventory_targeting = line_item.targeting.inventoryTargeting
                    if hasattr(inventory_targeting, 'targetedAdUnits'):
                        for ad_unit in inventory_targeting.targetedAdUnits:
                            ad_unit_ids.add(ad_unit.adUnitId)

    # Fetch Ad Unit names in bulk asynchronously in batches
    ad_unit_names_cache = await fetch_ad_unit_names_in_batches(client, list(ad_unit_ids))

    # Ensure that all names were fetched
    if 'error' in ad_unit_names_cache:
        return {"error": ad_unit_names_cache['error']}

    # Process results with cached Ad Unit names
    for line_item in response['results']:
        try:
            line_item_id = line_item.id
            name = line_item.name
            start_date_time = format_date_time(getattr(line_item, 'startDateTime', None))
            end_date_time = format_date_time(getattr(line_item, 'endDateTime', None))
            status = line_item.status
            targeting = getattr(line_item, 'targeting', None)

            # Parse targeting details using the bulk-fetched names
            targeting_details = get_targeting_details(client, targeting, ad_unit_names_cache) if targeting else {}

            results.append({
                "id": line_item_id,
                "name": name,
                "startDateTime": start_date_time,
                "endDateTime": end_date_time,
                "status": status,
                "targeting": targeting_details,
            })
        except Exception as e:
            results.append({
                "error": f"Error processing line item: {str(e)}"
            })

    return results


async def run_cli(json_output_file=None):
    """Run the script in CLI mode (for GitHub Actions)."""
    print("=" * 60)
    print("Today's Sponsorship Details")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Initialize Ad Manager client
        yaml_file = os.getenv('GAM_YAML_FILE', 'googleadsN.yaml')
        client = ad_manager.AdManagerClient.LoadFromStorage(yaml_file)
        print(f"[INFO] Loaded GAM client from {yaml_file}")
        
        data = await get_todays_sponsorships(client)
        
        # Prepare output structure
        output = {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "generated_by": "GAM Sponsorship Details Script",
            "total_items": 0,
            "data": [],
            "status": "success"
        }
        
        if isinstance(data, dict) and 'error' in data:
            print(f"[ERROR] {data['error']}")
            output["status"] = "error"
            output["error"] = data['error']
        elif not data:
            print("[INFO] No sponsorship line items found for today.")
            output["data"] = []
        else:
            output["data"] = data
            output["total_items"] = len(data)
            
            print(f"[INFO] Found {len(data)} sponsorship line items for today:")
            print()
            
            for item in data:
                if 'error' in item:
                    print(f"  [ERROR] {item['error']}")
                    continue
                
                print(f"  ID: {item['id']}")
                print(f"  Name: {item['name']}")
                print(f"  Status: {item['status']}")
                print(f"  Start: {item['startDateTime']}")
                print(f"  End: {item['endDateTime']}")
                
                if item.get('targeting', {}).get('inventoryTargeting'):
                    print("  Targeted Ad Units:")
                    for ad_unit in item['targeting']['inventoryTargeting']:
                        print(f"    - {ad_unit['AdunitName']} (ID: {ad_unit['adUnitId']})")
                print()
        
        # Save to JSON file if specified
        if json_output_file:
            with open(json_output_file, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"[INFO] JSON output saved to: {json_output_file}")
        
        # Also print JSON to console
        print("=" * 60)
        print("JSON Output:")
        print("=" * 60)
        print(json.dumps(output, indent=2))
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise


# Web server endpoint (only if Quart is available)
if app is not None:
    @app.route('/api/sponsorships', methods=['GET'])
    async def sponsorships_api():
        """API endpoint to fetch sponsorship line items for today asynchronously."""
        try:
            # Initialize Ad Manager client
            client = ad_manager.AdManagerClient.LoadFromStorage('googleadsN.yaml')
            data = await get_todays_sponsorships(client)
            return jsonify({"data": data, "status": "success"})
        except Exception as e:
            return jsonify({"message": str(e), "status": "error"})


if __name__ == '__main__':
    if '--cli' in sys.argv:
        # CLI mode for GitHub Actions
        # Check for --json-output argument
        json_output_file = None
        for i, arg in enumerate(sys.argv):
            if arg == '--json-output' and i + 1 < len(sys.argv):
                json_output_file = sys.argv[i + 1]
                break
        asyncio.run(run_cli(json_output_file))
    elif app is not None:
        # Web server mode
        app.run(host='0.0.0.0', port=5000)
    else:
        print("Error: Quart not installed. Run with --cli flag or install quart.")
        sys.exit(1)
