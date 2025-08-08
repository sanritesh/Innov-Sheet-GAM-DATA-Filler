import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleads import ad_manager
from datetime import datetime, timedelta
import pytz
import time
import re

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA')

# GAM setup
GAM_YAMLS = os.getenv('GAM_YAML_FILES', 'googleadsN.yaml,googleads.yaml').split(',')

# Exclusion list for Package Name (case-insensitive)
DEFAULT_EXCLUDE_SUBSTRINGS = [
    'ETCIO', 'ETBRANDEQUITY', 'ETHR', 'ETCFO', 'ETAUTO', 'ETRETAIL', 'ETHEALTH', 'ETTELECOM', 'ETENERGY',
    'ETREALESTATE', 'ETIT', 'ETITSECURITY', 'ETBFSI', 'ETGOVERNMENT', 'ETHOSPITALITY', 'ETLEGAL',
    'ETTRAVELWORLD', 'ETINFRA', 'ETB2B', 'ETCIOSEA', 'ETHRSEA', 'ETHREMEA', 'ETEduCation', 'ETEnergyWorldMEA',
    'ETManufacturing', 'ETPharma', 'ETGCC', 'ETEnterpriseAI', 'ETREALTY', 'ET ENERGY', 'ET TRAVEL', 'ET REALTY'
]
EXCLUDE_SUBSTRINGS = os.getenv('EXCLUDE_SUBSTRINGS', ','.join(DEFAULT_EXCLUDE_SUBSTRINGS)).split(',')

# Exclude platforms
EXCLUDE_PLATFORMS = os.getenv('EXCLUDE_PLATFORMS', 'App').split(',')

def setup_google_sheets():
    """Setup Google Sheets authentication using environment variables or fallback to file"""
    try:
        # Try to use service account JSON from environment
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            # Parse JSON and create credentials
            service_account_info = json.loads(service_account_json)
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                service_account_info, SCOPES
            )
            print("Using service account JSON from environment variable")
        else:
            # Fallback to file-based authentication
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                'service-account.json', SCOPES
            )
            print("Using service account JSON from file")
        
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        print(f"Error setting up Google Sheets: {e}")
        return None

def get_date_sheets(sh):
    """Get all sheets that follow any date pattern (today and future only)"""
    all_sheets = sh.worksheets()
    date_sheets = []
    # Use IST timezone for consistent date comparison
    tz = pytz.timezone('Asia/Kolkata')
    today = datetime.now(tz)
    
    print(f"[DEBUG] Found {len(all_sheets)} total sheets")
    print(f"[DEBUG] Sheet names: {[sheet.title for sheet in all_sheets]}")
    
    # Common date patterns to try
    date_patterns = [
        "%d %B",       # "26 July" (with leading zero)
        "%B %d",       # "July 26" (with leading zero)
        "%d %b",       # "26 Aug" (abbreviated month)
        "%b %d",       # "Aug 26" (abbreviated month)
        "%d/%m",       # "26/07" (with leading zero)
        "%m/%d",       # "07/26" (with leading zero)
        "%d-%m",       # "26-07" (with leading zero)
        "%m-%d",       # "07-26" (with leading zero)
        "%d.%m",       # "26.07" (with leading zero)
        "%m.%d",       # "07.26" (with leading zero)
        "%d %B %Y",    # "26 July 2025" (with leading zero)
        "%B %d %Y",    # "July 26 2025" (with leading zero)
        "%d %b %Y",    # "26 Aug 2025" (abbreviated month)
        "%b %d %Y",    # "Aug 26 2025" (abbreviated month)
        "%d/%m/%Y",    # "26/07/2025" (with leading zero)
        "%m/%d/%Y",    # "07/26/2025" (with leading zero)
        "%d-%m-%Y",    # "26-07-2025" (with leading zero)
        "%m-%d-%Y",    # "07-26-2025" (with leading zero)
        "%d.%m.%Y",    # "26.07.2025" (with leading zero)
        "%m.%d.%Y",    # "07.26.2025" (with leading zero)
    ]
    
    # Try to parse with flexible day format (handle both single and double digit days)
    def try_parse_date(sheet_title):
        print(f"[DEBUG]   Trying to parse: '{sheet_title}'")
        # First try the standard patterns
        for pattern in date_patterns:
            try:
                date_obj = datetime.strptime(sheet_title, pattern)
                if date_obj.year >= 2020:
                    # Make timezone-aware for proper comparison
                    tz_aware_date = tz.localize(date_obj)
                    print(f"[DEBUG]   Successfully parsed with pattern '{pattern}': {tz_aware_date}")
                    return tz_aware_date
            except ValueError:
                continue
        
        # If standard patterns fail, try to handle single-digit days manually
        # Look for patterns like "1 July", "2 Aug", etc.
        import re
        match = re.match(r'^(\d{1,2})\s+([A-Za-z]+)$', sheet_title)
        if match:
            day_str, month_str = match.groups()
            print(f"[DEBUG]   Regex matched: day='{day_str}', month='{month_str}'")
            try:
                # Try to parse with the day as-is, first with full month name
                date_str = f"{day_str} {month_str} 2025"
                date_obj = datetime.strptime(date_str, "%d %B %Y")
                if date_obj.year >= 2020:
                    # Make timezone-aware for proper comparison
                    tz_aware_date = tz.localize(date_obj)
                    print(f"[DEBUG]   Successfully parsed with full month: {tz_aware_date}")
                    return tz_aware_date
            except ValueError:
                try:
                    # Try with abbreviated month name
                    date_obj = datetime.strptime(date_str, "%d %b %Y")
                    if date_obj.year >= 2020:
                        # Make timezone-aware for proper comparison
                        tz_aware_date = tz.localize(date_obj)
                        print(f"[DEBUG]   Successfully parsed with abbreviated month: {tz_aware_date}")
                        return tz_aware_date
                except ValueError:
                    print(f"[DEBUG]   Failed to parse '{date_str}' with both full and abbreviated month patterns")
                    pass
        
        print(f"[DEBUG]   No pattern matched for '{sheet_title}'")
        return None
    
    for sheet in all_sheets:
        sheet_title = sheet.title.strip()
        print(f"[DEBUG] Checking sheet: '{sheet_title}'")
        
        # Skip if sheet title is too short or doesn't contain numbers
        if len(sheet_title) < 3 or not re.search(r'\d', sheet_title):
            print(f"[DEBUG]   Skipping '{sheet_title}' - too short or no numbers")
            continue
            
        # Try to parse the date
        date_obj = try_parse_date(sheet_title)
        if date_obj:
            # Only include today and future dates
            if date_obj.date() >= today.date():
                date_sheets.append((sheet, date_obj))
                print(f"[DEBUG]   Matched '{sheet_title}' -> {date_obj} (future/today)")
            else:
                print(f"[DEBUG]   Skipping '{sheet_title}' -> {date_obj} (past date)")
        else:
            print(f"[DEBUG]   No pattern matched for '{sheet_title}'")
    
    # Sort by date (newest first)
    date_sheets.sort(key=lambda x: x[1], reverse=True)
    print(f"[DEBUG] Found {len(date_sheets)} date-based sheets (today and future)")
    return date_sheets

def needs_updating(ws):
    """Check if a sheet needs updating (has rows with empty geo columns)"""
    try:
        # Get all values from the sheet
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:  # No data or only header
            return True
        
        # Find our target columns
        header = all_values[0]
        geo_included_idx = None
        geo_excluded_idx = None
        
        for i, col in enumerate(header):
            if col and col.strip() == 'geo included':
                geo_included_idx = i
            elif col and col.strip() == 'geo excluded':
                geo_excluded_idx = i
        
        # If our columns don't exist, sheet needs updating
        if geo_included_idx is None or geo_excluded_idx is None:
            return True
        
        # Check if any rows have empty geo data
        rows_needing_update = 0
        for row_idx, row in enumerate(all_values[1:], start=2):  # Skip header, start from row 2
            if len(row) > max(geo_included_idx, geo_excluded_idx):
                geo_included_val = str(row[geo_included_idx]).strip() if row[geo_included_idx] else ''
                geo_excluded_val = str(row[geo_excluded_idx]).strip() if row[geo_excluded_idx] else ''
                
                # Check if this row has a campaign name but empty geo data
                campaign_name_idx = None
                for i, col in enumerate(header):
                    if col and col.strip() == 'Campaign Name':
                        campaign_name_idx = i
                        break
                
                if campaign_name_idx is not None and campaign_name_idx < len(row):
                    campaign_name = str(row[campaign_name_idx]).strip() if row[campaign_name_idx] else ''
                    if campaign_name and (not geo_included_val and not geo_excluded_val):
                        rows_needing_update += 1
        
        if rows_needing_update > 0:
            print(f"[INFO] Sheet {ws.title} needs updating - {rows_needing_update} rows with empty geo data")
            return True
        else:
            print(f"[INFO] Sheet {ws.title} is already complete - all rows have geo data")
            return False
        
    except Exception as e:
        print(f"[ERROR] Checking if sheet needs updating: {e}")
        return True  # Assume it needs updating if we can't check

def find_sheets_to_update(sh):
    """Find sheets that need updating from the last 5 date-based sheets"""
    date_sheets = get_date_sheets(sh)
    
    if not date_sheets:
        print("[WARNING] No date-based sheets found")
        return []
    
    print(f"[INFO] Found {len(date_sheets)} date-based sheets")
    
    # Check the last 5 sheets (or all if less than 5)
    sheets_to_check = date_sheets[:5]
    sheets_to_update = []
    
    for sheet, date in sheets_to_check:
        print(f"[INFO] Checking sheet: {sheet.title} ({date.strftime('%B %-d')})")
        if needs_updating(sheet):
            print(f"[INFO] Sheet {sheet.title} needs updating")
            sheets_to_update.append(sheet)
        else:
            print(f"[INFO] Sheet {sheet.title} already updated")
    
    return sheets_to_update

# Authenticate Google Sheets using environment variables or fallback
gc = setup_google_sheets()
if not gc:
    print("[ERROR] Failed to setup Google Sheets authentication")
    exit(1)

sh = gc.open_by_key(SHEET_ID)

# Find sheets that need updating
sheets_to_update = find_sheets_to_update(sh)

if not sheets_to_update:
    print("[INFO] All sheets are already updated. No work needed.")
    exit(0)

print(f"[INFO] Found {len(sheets_to_update)} sheets that need updating")

# Authenticate both GAM clients
clients = [ad_manager.AdManagerClient.LoadFromStorage(yaml) for yaml in GAM_YAMLS]

tz = pytz.timezone('Asia/Kolkata')
now = datetime.now(tz)

# Helper to extract geo info from a line item
def extract_geo(line_item):
    geo = {'included': [], 'excluded': []}
    try:
        if hasattr(line_item, 'targeting') and hasattr(line_item.targeting, 'geoTargeting'):
            geoTargeting = line_item.targeting.geoTargeting
            if hasattr(geoTargeting, 'targetedLocations'):
                for loc in geoTargeting.targetedLocations:
                    geo['included'].append({
                        'id': str(getattr(loc, 'id', '')),
                        'name': getattr(loc, 'displayName', ''),
                        'type': getattr(loc, 'type', '')
                    })
            if hasattr(geoTargeting, 'excludedLocations'):
                for loc in geoTargeting.excludedLocations:
                    geo['excluded'].append({
                        'id': str(getattr(loc, 'id', '')),
                        'name': getattr(loc, 'displayName', ''),
                        'type': getattr(loc, 'type', '')
                    })
    except Exception as e:
        print(f"[ERROR] Extracting geo: {e}")
    return geo

# Cache to store results for Expresso ID + Campaign Name combinations
result_cache = {}

# For each campaign name, find matching active sponsorship order/line-item and fetch geo
def is_active_sponsorship(li):
    try:
        # Check if line item type is SPONSORSHIP
        if getattr(li, 'lineItemType', '') != 'SPONSORSHIP':
            return False
        
        # Check if line item status is not COMPLETED
        line_item_status = getattr(li, 'status', '')
        if line_item_status == 'COMPLETED':
            print(f"[DEBUG] Skipping line item with COMPLETED status")
            return False
        
        start = getattr(li, 'startDateTime', None)
        end = getattr(li, 'endDateTime', None)
        if not start or not end:
            return False
        
        # Parse start date
        start_date = getattr(start, 'date', None)
        start_hour = getattr(start, 'hour', 0)
        start_minute = getattr(start, 'minute', 0)
        start_second = getattr(start, 'second', 0)
        
        if start_date:
            start_year = getattr(start_date, 'year', 0)
            start_month = getattr(start_date, 'month', 0)
            start_day = getattr(start_date, 'day', 0)
        else:
            start_year = getattr(start, 'year', 0)
            start_month = getattr(start, 'month', 0)
            start_day = getattr(start, 'day', 0)
        
        # Parse end date
        end_date = getattr(end, 'date', None)
        end_hour = getattr(end, 'hour', 23)
        end_minute = getattr(end, 'minute', 59)
        end_second = getattr(end, 'second', 59)
        
        if end_date:
            end_year = getattr(end_date, 'year', 0)
            end_month = getattr(end_date, 'month', 0)
            end_day = getattr(end_date, 'day', 0)
        else:
            end_year = getattr(end, 'year', 0)
            end_month = getattr(end, 'month', 0)
            end_day = getattr(end, 'day', 0)
        
        # Create datetime objects
        start_dt = datetime(start_year, start_month, start_day, start_hour, start_minute, start_second, tzinfo=tz)
        end_dt = datetime(end_year, end_month, end_day, end_hour, end_minute, end_second, tzinfo=tz)
        
        # Get current date (date only, no time)
        current_date = now.date()
        tomorrow_date = current_date + timedelta(days=1)
        day_after_tomorrow = current_date + timedelta(days=2)
        start_date_only = start_dt.date()
        end_date_only = end_dt.date()
        
        # Filter 1: Exclude if both start and end dates are in the past
        if start_date_only < current_date and end_date_only < current_date:
            print(f"[DEBUG] Skipping line item with past date range: start={start_date_only}, end={end_date_only} < {current_date}")
            return False
        
        # NEW: Exclude line items that start on T+2 (day after tomorrow) - they won't run tomorrow
        if start_date_only >= day_after_tomorrow:
            print(f"[DEBUG] Skipping line item starting on T+2 or later: start={start_date_only} >= {day_after_tomorrow}")
            return False
        
        # NEW: Exclude same-day campaigns (start and end on today)
        if start_date_only == current_date and end_date_only == current_date:
            print(f"[DEBUG] Skipping same-day line item: start={start_date_only}, end={end_date_only} == {current_date}")
            return False
        
        # Include line items that are already running (start date is today or earlier) AND have future end date
        if start_date_only <= current_date and end_date_only > current_date:
            print(f"[DEBUG] Including line item already running with future end: start={start_date_only} <= {current_date}, end={end_date_only} > {current_date}")
            return True
        
        # Include line items that start tomorrow
        if start_date_only == tomorrow_date:
            print(f"[DEBUG] Including line item starting tomorrow: start={start_date_only} == {tomorrow_date}")
            return True
        
        # Exclude line items that start on T+2 or later
        print(f"[DEBUG] Skipping line item with future start date: start={start_date_only} > {tomorrow_date}")
        return False
        
    except Exception as e:
        print(f"[ERROR] Checking active sponsorship: {e}")
        return False

def is_valid_order(order):
    """Check if order is valid (not completed and has valid date range)"""
    try:
        # Check if order status is not COMPLETED
        order_status = getattr(order, 'status', '')
        if order_status == 'COMPLETED':
            print(f"[DEBUG] Skipping order with COMPLETED status")
            return False
        
        # Check order start and end dates (if available)
        start = getattr(order, 'startDateTime', None)
        end = getattr(order, 'endDateTime', None)
        
        if start and end:
            start_date = getattr(start, 'date', None)
            end_date = getattr(end, 'date', None)
            
            if start_date and end_date:
                start_year = getattr(start_date, 'year', 0)
                start_month = getattr(start_date, 'month', 0)
                start_day = getattr(start_date, 'day', 0)
                
                end_year = getattr(end_date, 'year', 0)
                end_month = getattr(end_date, 'month', 0)
                end_day = getattr(end_date, 'day', 0)
                
                start_dt = datetime(start_year, start_month, start_day, 0, 0, 0, tzinfo=tz)
                end_dt = datetime(end_year, end_month, end_day, 23, 59, 59, tzinfo=tz)
                
                current_date = now.date()
                tomorrow_date = current_date + timedelta(days=1)
                day_after_tomorrow = current_date + timedelta(days=2)
                start_date_only = start_dt.date()
                end_date_only = end_dt.date()
                
                # Check if both start and end dates are in the past
                if start_date_only < current_date and end_date_only < current_date:
                    print(f"[DEBUG] Skipping order with past date range: start={start_date_only}, end={end_date_only} < {current_date}")
                    return False
                
                # Exclude orders that start on T+2 (day after tomorrow) - they won't run tomorrow
                if start_date_only >= day_after_tomorrow:
                    print(f"[DEBUG] Skipping order starting on T+2 or later: start={start_date_only} >= {day_after_tomorrow}")
                    return False
                
                # Exclude same-day campaigns (start and end on today)
                if start_date_only == current_date and end_date_only == current_date:
                    print(f"[DEBUG] Skipping same-day campaign: start={start_date_only}, end={end_date_only} == {current_date}")
                    return False
                
                # Include orders that are already running (start date is today or earlier) AND have future end date
                if start_date_only <= current_date and end_date_only > current_date:
                    print(f"[DEBUG] Including order already running with future end: start={start_date_only} <= {current_date}, end={end_date_only} > {current_date}")
                    return True
                
                # Include orders that start tomorrow
                if start_date_only == tomorrow_date:
                    print(f"[DEBUG] Including order starting tomorrow: start={start_date_only} == {tomorrow_date}")
                    return True
                
                # Exclude orders that start on T+2 or later
                print(f"[DEBUG] Skipping order with future start date: start={start_date_only} > {tomorrow_date}")
                return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Checking order validity: {e}")
        return False

def process_single_order(order, client, order_name, order_id):
    """Process a single order and return its information including geo, trafficker, creator"""
    try:
        # Get client network code for identification
        client_network = str(getattr(client, 'network_code', 'unknown'))
        # Get line items for this order
        line_item_service = client.GetService('LineItemService', version='v202411')
        
        statement = ad_manager.StatementBuilder().Where('orderId = :order_id').WithBindVariable('order_id', order_id)
        line_items = line_item_service.getLineItemsByStatement(statement.ToStatement())
        
        print(f"[DEBUG] Found {len(line_items) if line_items else 0} line items for order {order_id}")
        
        if line_items and len(line_items) > 0:
            # Access the results array from LineItemPage
            if hasattr(line_items, 'results'):
                line_item_results = line_items.results
            else:
                line_item_results = line_items
            
            for li in line_item_results:
                try:
                    if hasattr(li, 'name'):
                        li_name = li.name
                        li_type = li.lineItemType
                    elif isinstance(li, dict):
                        li_name = li.get('name', 'Unknown')
                        li_type = li.get('lineItemType', 'Unknown')
                    else:
                        print(f"[DEBUG]   Unknown line item structure: {li}")
                        continue
                    
                    print(f"[DEBUG]   Line item: {li_name}, type: {li_type}")
                    
                    # Check if line item is active and of type SPONSORSHIP
                    if is_active_sponsorship(li):
                        print(f"[DEBUG]     Line item is active and of type SPONSORSHIP")
                        geo = extract_geo(li)
                        
                        # Get order info
                        order_info = {
                            'order_id': order_id,
                            'order_name': order_name,
                            'client_network': client_network,
                            'trafficker_id': order.traffickerId if hasattr(order, 'traffickerId') else None,
                            'creator_id': order.creatorId if hasattr(order, 'creatorId') else None,
                            'geo_included': geo['included'],
                            'geo_excluded': geo['excluded']
                        }
                        print(f"[DEBUG] Order info created with client_network: '{client_network}' (type: {type(client_network)})")
                        
                        # Get trafficker and creator names
                        try:
                            user_service = client.GetService('UserService', version='v202411')
                            if order_info['trafficker_id']:
                                trafficker_statement = ad_manager.StatementBuilder().Where('id = :user_id').WithBindVariable('user_id', order_info['trafficker_id'])
                                trafficker_users = user_service.getUsersByStatement(trafficker_statement.ToStatement())
                                if trafficker_users and len(trafficker_users) > 0:
                                    if hasattr(trafficker_users, 'results') and trafficker_users.results:
                                        order_info['trafficker_name'] = trafficker_users.results[0].name
                            
                            if order_info['creator_id']:
                                creator_statement = ad_manager.StatementBuilder().Where('id = :user_id').WithBindVariable('user_id', order_info['creator_id'])
                                creator_users = user_service.getUsersByStatement(creator_statement.ToStatement())
                                if creator_users and len(creator_users) > 0:
                                    if hasattr(creator_users, 'results') and creator_users.results:
                                        order_info['creator_name'] = creator_users.results[0].name
                        except Exception as e:
                            print(f"[ERROR] Getting user names: {e}")
                        
                        print(f"[DEBUG]     Geo included: {geo['included']}, Geo excluded: {geo['excluded']}")
                        return order_info
                    else:
                        print(f"[DEBUG]     Line item is NOT active or not SPONSORSHIP")
                except Exception as e:
                    print(f"[DEBUG] Error processing line item: {e}")
                    continue
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Processing single order: {e}")
        return None

def fetch_geo_for_search_string(search_string, clients, package_id=None):
    """Fetch geo information for all valid orders matching the search string"""
    all_orders_info = []  # List to store multiple order information
    
    for client in clients:
        try:
            print(f"[DEBUG] Trying client with network code: {client.network_code}")
            
            # First try to find orders containing the search string
            order_service = client.GetService('OrderService', version='v202411')
            print(f"[DEBUG] Using OrderService with v202411")
            
            statement = ad_manager.StatementBuilder().Where('name LIKE :search_string').WithBindVariable('search_string', f'%{search_string}%')
            orders = order_service.getOrdersByStatement(statement.ToStatement())
            
            print(f"[DEBUG] Search for '{search_string}' returned {len(orders) if orders else 0} orders")
            
            if orders and len(orders) > 0:
                try:
                    print(f"[DEBUG] Orders structure: {type(orders)}")
                    print(f"[DEBUG] Orders length: {len(orders)}")
                    
                    # For OrderPage objects, we need to access the results differently
                    if hasattr(orders, 'results'):
                        # Try to access the results attribute
                        order_results = orders.results
                        if order_results and len(order_results) > 0:
                            print(f"[DEBUG] Found {len(order_results)} orders, processing all valid ones")
                            
                            # Process all orders, not just the first one
                            for order in order_results:
                                print(f"[DEBUG] Processing order: {order}")
                                print(f"[DEBUG] Order type: {type(order)}")
                                
                                # Check if order is valid (not completed, future start date)
                                if not is_valid_order(order):
                                    print(f"[DEBUG] Skipping invalid order")
                                    continue
                                
                                if hasattr(order, 'name'):
                                    order_name = order.name
                                    order_id = order.id
                                elif isinstance(order, dict):
                                    order_name = order.get('name', 'Unknown')
                                    order_id = order.get('id', 'Unknown')
                                else:
                                    print(f"[DEBUG] Unknown order structure: {order}")
                                    continue
                                
                                print(f"[DEBUG] Found valid order: {order_name} (ID: {order_id})")
                                
                                # Add Package ID validation check
                                if package_id and package_id.strip():
                                    if package_id.strip() not in order_name:
                                        print(f"[DEBUG] Skipping order '{order_name}' - Package ID '{package_id}' not found in order name")
                                        continue
                                    else:
                                        print(f"[DEBUG] Order '{order_name}' contains Package ID '{package_id}' - proceeding")
                                
                                # Process this order and get its information
                                order_info = process_single_order(order, client, order_name, order_id)
                                if order_info:
                                    all_orders_info.append(order_info)
                        else:
                            print(f"[DEBUG] No results in OrderPage")
                            continue
                    else:
                        print(f"[DEBUG] Orders object has no 'results' attribute: {orders}")
                        continue
                except Exception as e:
                    print(f"[DEBUG] Error accessing order details: {e}")
                    print(f"[DEBUG] Full error: {type(e).__name__}: {str(e)}")
                    continue
            
            # If no orders found, try direct line item search
            print(f"[DEBUG] No orders found containing '{search_string}', trying direct line item search...")
            line_item_service = client.GetService('LineItemService', version='v202411')
            print(f"[DEBUG] Using LineItemService with v202411")
            
            statement = ad_manager.StatementBuilder().Where('name LIKE :search_string').WithBindVariable('search_string', f'%{search_string}%')
            line_items = line_item_service.getLineItemsByStatement(statement.ToStatement())
            
            print(f"[DEBUG] Search for '{search_string}' returned {len(line_items) if line_items else 0} line items")
            
            if line_items and len(line_items) > 0:
                # Access the results array from LineItemPage
                if hasattr(line_items, 'results'):
                    line_item_results = line_items.results
                else:
                    line_item_results = line_items
                
                for li in line_item_results:
                    try:
                        if hasattr(li, 'name'):
                            li_name = li.name
                            li_type = li.lineItemType
                        elif isinstance(li, dict):
                            li_name = li.get('name', 'Unknown')
                            li_type = li.get('lineItemType', 'Unknown')
                        else:
                            print(f"[DEBUG]   Unknown line item structure: {li}")
                            continue
                        
                        print(f"[DEBUG]   Line item: {li_name}, type: {li_type}")
                        
                        if is_active_sponsorship(li):
                            print(f"[DEBUG]     Line item is active and of type SPONSORSHIP")
                            geo = extract_geo(li)
                            all_included.extend(geo['included'])
                            all_excluded.extend(geo['excluded'])
                            
                            # Get order info for this line item
                            order_id = li.orderId if hasattr(li, 'orderId') else None
                            if order_id:
                                order_statement = ad_manager.StatementBuilder().Where('id = :order_id').WithBindVariable('order_id', order_id)
                                orders = order_service.getOrdersByStatement(order_statement.ToStatement())
                                if orders and len(orders) > 0:
                                    if hasattr(orders, 'results') and orders.results:
                                        first_order = orders.results[0]
                                        
                                        # Check if order is valid (not completed, future start date)
                                        if not is_valid_order(first_order):
                                            print(f"[DEBUG] Skipping line item due to invalid order")
                                            continue
                                        
                                        order_info = {
                                            'order_id': first_order.id,
                                            'client_network': client_network,
                                            'trafficker_id': first_order.traffickerId if hasattr(first_order, 'traffickerId') else None,
                                            'creator_id': first_order.creatorId if hasattr(first_order, 'creatorId') else None
                                        }
                                        
                                        # Get trafficker and creator names
                                        try:
                                            user_service = client.GetService('UserService', version='v202411')
                                            if order_info['trafficker_id']:
                                                trafficker_statement = ad_manager.StatementBuilder().Where('id = :user_id').WithBindVariable('user_id', order_info['trafficker_id'])
                                                trafficker_users = user_service.getUsersByStatement(trafficker_statement.ToStatement())
                                                if trafficker_users and len(trafficker_users) > 0:
                                                    if hasattr(trafficker_users, 'results') and trafficker_users.results:
                                                        order_info['trafficker_name'] = trafficker_users.results[0].name
                                            
                                            if order_info['creator_id']:
                                                creator_statement = ad_manager.StatementBuilder().Where('id = :user_id').WithBindVariable('user_id', order_info['creator_id'])
                                                creator_users = user_service.getUsersByStatement(creator_statement.ToStatement())
                                                if creator_users and len(creator_users) > 0:
                                                    if hasattr(creator_users, 'results') and creator_users.results:
                                                        order_info['creator_name'] = creator_users.results[0].name
                                        except Exception as e:
                                            print(f"[ERROR] Getting user names: {e}")
                            
                            print(f"[DEBUG]     Geo included: {geo['included']}, Geo excluded: {geo['excluded']}")
                            
                            # Add order name to the order info
                            order_info['order_name'] = first_order.name if hasattr(first_order, 'name') else 'Unknown'
                            order_info['geo_included'] = geo['included']
                            order_info['geo_excluded'] = geo['excluded']
                            
                            all_orders_info.append(order_info)
                            return all_orders_info
                        else:
                            print(f"[DEBUG]     Line item is NOT active or not SPONSORSHIP")
                    except Exception as e:
                        print(f"[DEBUG] Error processing line item: {e}")
                        continue
            else:
                print(f"[DEBUG] No line items found containing '{search_string}' in any GAM account")
                
        except Exception as e:
            print(f"[ERROR] Processing client: {e}")
            print(f"[DEBUG] Full error details: {type(e).__name__}: {str(e)}")
            continue
    
    return all_orders_info

def process_sheet(ws):
    """Process a single sheet and update it with geo information"""
    print(f"\n[INFO] Processing sheet: {ws.title}")
    
    # Read all campaign names from the sheet
    try:
        rows = ws.get_all_records()
    except gspread.exceptions.GSpreadException as e:
        print(f"[WARNING] Sheet {ws.title} has header issues, trying to fix...")
        # Try to get records with explicit headers
        all_values = ws.get_all_values()
        if all_values and len(all_values) > 1:
            # Use the first row as headers, skip empty columns
            header_row = []
            for col in all_values[0]:
                col_str = str(col).strip() if col else ''
                if col_str:
                    header_row.append(col_str)
                else:
                    header_row.append(f"Column_{len(header_row)}")  # Give empty columns a name
            
            data_rows = all_values[1:]
            
            # Create records manually
            rows = []
            for row in data_rows:
                if len(row) >= len(header_row):
                    record = {}
                    for i, header in enumerate(header_row):
                        if i < len(row):
                            record[header] = row[i]
                        else:
                            record[header] = ''
                    rows.append(record)
            
            print(f"[INFO] Successfully processed sheet with {len(rows)} rows using {len(header_row)} headers")
        else:
            print(f"[ERROR] Could not process sheet {ws.title} due to header issues")
            return
    
    if not rows:
        print(f"[INFO] No data found in sheet {ws.title}")
        return
    
    # Filter out rows without campaign names
    valid_rows = []
    for row in rows:
        campaign_name = row.get('Campaign Name')
        if campaign_name:
            # Convert to string and check if it's not empty after stripping
            campaign_name_str = str(campaign_name).strip()
            if campaign_name_str:
                valid_rows.append(row)
    if not valid_rows:
        print(f"[INFO] No valid campaign names found in sheet {ws.title}")
        return
    
    print(f"[INFO] Found {len(valid_rows)} rows with valid campaign names in sheet {ws.title}")
    
    campaign_names = [str(row['Campaign Name']).strip() for row in valid_rows]
    
    # Prepare to update sheet with separate columns for each GAM client
    geo_included_col = 'geo included'
    geo_excluded_col = 'geo excluded'
    
    # Client 1 (Network 23037861279) columns
    order_id_col_1 = 'Order ID (23037861279)'
    order_name_col_1 = 'Order Name (23037861279)'
    trafficker_col_1 = 'Trafficker (23037861279)'
    creator_col_1 = 'Creator (23037861279)'
    
    # Client 2 (Network 7176) columns
    order_id_col_2 = 'Order ID (7176)'
    order_name_col_2 = 'Order Name (7176)'
    trafficker_col_2 = 'Trafficker (7176)'
    creator_col_2 = 'Creator (7176)'
    
    header = ws.row_values(1)
    
    # Find the Placement column index
    placement_idx = None
    for i, col in enumerate(header):
        if col == 'Placement':
            placement_idx = i
            break
    
    if placement_idx is None:
        print(f"[ERROR] 'Placement' column not found in sheet {ws.title}")
        return
    
    print(f"[INFO] Found 'Placement' column at index {placement_idx} in sheet {ws.title}")
    
    # Check for existing empty columns after Placement
    empty_cols_after_placement = []
    for i in range(placement_idx + 1, len(header)):
        header_val = str(header[i]).strip() if header[i] else ''
        if not header_val:
            empty_cols_after_placement.append(i)
    
    print(f"[INFO] Found {len(empty_cols_after_placement)} empty columns after Placement")
    
    # Define the columns we need to add
    required_columns = [
        geo_included_col, geo_excluded_col,
        order_id_col_1, order_name_col_1, trafficker_col_1, creator_col_1,
        order_id_col_2, order_name_col_2, trafficker_col_2, creator_col_2
    ]
    
    # Check which columns already exist
    existing_columns = {}
    missing_columns = []
    
    for col in required_columns:
        if col in header:
            existing_columns[col] = header.index(col)
        else:
            missing_columns.append(col)
    
    print(f"[INFO] Existing columns: {list(existing_columns.keys())}")
    print(f"[INFO] Missing columns: {missing_columns}")
    
    # Add missing columns after Placement
    if missing_columns:
        if len(empty_cols_after_placement) >= len(missing_columns):
            # Use existing empty columns
            for i, col in enumerate(missing_columns):
                col_idx = empty_cols_after_placement[i]
                ws.update_cell(1, col_idx + 1, col)  # +1 because gspread uses 1-based indexing
                header[col_idx] = col
                print(f"[INFO] Added '{col}' to existing empty column {col_idx + 1}")
        else:
            # Check if we can add new columns at the end
            current_column_count = len(header)
            required_new_columns = len(missing_columns)
            
            # Try to resize the grid if we're at the limit
            if current_column_count + required_new_columns > len(header) or current_column_count + required_new_columns > 26:
                try:
                    # Resize the grid to accommodate more columns
                    new_column_count = current_column_count + required_new_columns + 5  # Add extra buffer
                    print(f"[INFO] Resizing grid from {current_column_count} to {new_column_count} columns")
                    
                    # Get the spreadsheet object to resize
                    spreadsheet = ws.spreadsheet
                    spreadsheet.batch_update({
                        'requests': [{
                            'updateSheetProperties': {
                                'properties': {
                                    'sheetId': ws.id,
                                    'gridProperties': {
                                        'columnCount': new_column_count
                                    }
                                },
                                'fields': 'gridProperties.columnCount'
                            }
                        }]
                    })
                    
                    print(f"[INFO] Successfully resized grid to {new_column_count} columns")
                    
                    # Update header length to reflect new grid size
                    header.extend([''] * (new_column_count - current_column_count))
                    
                    # Refresh the header to get the actual current state
                    header = ws.row_values(1)
                    print(f"[INFO] Refreshed header, now has {len(header)} columns")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to resize grid: {e}")
                    print(f"[ERROR] Cannot add {required_new_columns} new columns. Current columns: {current_column_count}")
                    print(f"[ERROR] Missing columns that need to be added: {missing_columns}")
                    print(f"[ERROR] Please manually add these columns after the 'Placement' column in the sheet '{ws.title}'")
                    print(f"[ERROR] Required columns: {missing_columns}")
                    return
            
            # Add new columns at the end
            current_end = len(header)
            for col in missing_columns:
                try:
                    ws.update_cell(1, current_end + 1, col)
                    header.append(col)
                    current_end += 1
                    print(f"[INFO] Added '{col}' as new column {current_end}")
                except Exception as e:
                    print(f"[ERROR] Failed to add column '{col}': {e}")
                    print(f"[ERROR] This might be due to sheet column limits. Please check the sheet '{ws.title}'")
                    return
    
    # Update header indices for existing columns
    for col in required_columns:
        if col in header:
            existing_columns[col] = header.index(col)
    
    # Process each row in the sheet
    for i, row in enumerate(valid_rows, start=2):  # Start from row 2 (after header)
        try:
            campaign_name = str(row.get('Campaign Name', '')).strip()
            expresso_id = str(row.get('Expresso ID', '')).strip()
            package_name = str(row.get('Package Name', '')).strip()
            package_id = str(row.get('Package ID', '')).strip()
            platform = str(row.get('Platform', '')).strip()
            
            # Skip if Platform is 'App'
            if platform == 'App':
                print(f"[SKIP] Row {i} skipped due to Platform 'App'.")
                continue
            
            # Skip if Package Name contains excluded substrings
            if any(substring.lower() in package_name.lower() for substring in EXCLUDE_SUBSTRINGS):
                print(f"[SKIP] Row {i} skipped due to excluded Package Name.")
                continue
            
            if not campaign_name:
                continue
            
            print(f"[INFO] Processing campaign: {campaign_name}")
            
            # Check cache first
            cache_key = f"{expresso_id}_{campaign_name}_{package_id}" if package_id else f"{expresso_id}_{campaign_name}"
            if cache_key in result_cache:
                print(f"[CACHE] Using cached results for: {cache_key}")
                all_orders_info = result_cache[cache_key]
            else:
                # Try to find geo using campaign name
                all_orders_info = fetch_geo_for_search_string(campaign_name, clients, package_id)
                
                # If no orders found, try using Expresso ID
                if not all_orders_info and expresso_id:
                    print(f"[INFO] No orders found for campaign, trying Expresso ID: {expresso_id}")
                    all_orders_info = fetch_geo_for_search_string(str(expresso_id), clients, package_id)
                
                # Cache the results
                result_cache[cache_key] = all_orders_info
            
            # Update the sheet with geo information for all orders
            if all_orders_info:
                # Get column indices
                geo_included_idx = existing_columns.get(geo_included_col, -1) + 1
                geo_excluded_idx = existing_columns.get(geo_excluded_col, -1) + 1
                
                # Check if all required columns exist
                geo_included_idx = existing_columns.get(geo_included_col, -1) + 1
                geo_excluded_idx = existing_columns.get(geo_excluded_col, -1) + 1
                
                # Client 1 columns
                order_id_idx_1 = existing_columns.get(order_id_col_1, -1) + 1
                order_name_idx_1 = existing_columns.get(order_name_col_1, -1) + 1
                trafficker_idx_1 = existing_columns.get(trafficker_col_1, -1) + 1
                creator_idx_1 = existing_columns.get(creator_col_1, -1) + 1
                
                # Client 2 columns
                order_id_idx_2 = existing_columns.get(order_id_col_2, -1) + 1
                order_name_idx_2 = existing_columns.get(order_name_col_2, -1) + 1
                trafficker_idx_2 = existing_columns.get(trafficker_col_2, -1) + 1
                creator_idx_2 = existing_columns.get(creator_col_2, -1) + 1
                
                if -1 in [geo_included_idx, geo_excluded_idx, order_id_idx_1, order_name_idx_1, trafficker_idx_1, creator_idx_1, order_id_idx_2, order_name_idx_2, trafficker_idx_2, creator_idx_2]:
                    print(f"[ERROR] Some required columns are missing in sheet {ws.title}")
                    continue
                
                # Collect all updates for this sheet to batch them
                all_cell_updates = []
                
                # Process each order found
                for order_idx, order_info in enumerate(all_orders_info):
                    # Prepare values for this order
                    geo_included_str = ', '.join([loc['name'] for loc in order_info.get('geo_included', [])]) if order_info.get('geo_included') else ''
                    geo_excluded_str = ', '.join([loc['name'] for loc in order_info.get('geo_excluded', [])]) if order_info.get('geo_excluded') else ''
                    order_id_str = str(order_info.get('order_id', '')) if order_info else ''
                    order_name_str = order_info.get('order_name', '') if order_info else ''
                    trafficker_str = order_info.get('trafficker_name', '') if order_info else ''
                    creator_str = order_info.get('creator_name', '') if order_info else ''
                    client_network = str(order_info.get('client_network', 'unknown'))
                    
                    # If this is the first order, update the existing row
                    if order_idx == 0:
                        current_row = i
                    else:
                        # For additional orders, only add new row if order name is different
                        previous_order_name = all_orders_info[order_idx - 1].get('order_name', '')
                        if order_name_str != previous_order_name:
                            # Insert a new row with the same data as the original row
                            current_row = i + order_idx
                            ws.insert_row([row.get(col, '') for col in header], current_row)
                            print(f"[INFO] Inserted new row {current_row} for different order: {order_name_str}")
                        else:
                            # Use the same row for orders with same name
                            current_row = i + order_idx - 1
                            print(f"[INFO] Using existing row {current_row} for duplicate order name: {order_name_str}")
                    
                    # Collect updates for this order based on client network
                    if geo_included_str:
                        all_cell_updates.append(gspread.Cell(current_row, geo_included_idx, geo_included_str))
                    if geo_excluded_str:
                        all_cell_updates.append(gspread.Cell(current_row, geo_excluded_idx, geo_excluded_str))
                    
                    # Use appropriate columns based on client network
                    if client_network == '23037861279':  # Client 1
                        if order_id_str:
                            all_cell_updates.append(gspread.Cell(current_row, order_id_idx_1, order_id_str))
                        if order_name_str:
                            all_cell_updates.append(gspread.Cell(current_row, order_name_idx_1, order_name_str))
                        if trafficker_str:
                            all_cell_updates.append(gspread.Cell(current_row, trafficker_idx_1, trafficker_str))
                        if creator_str:
                            all_cell_updates.append(gspread.Cell(current_row, creator_idx_1, creator_str))
                    elif client_network == '7176':  # Client 2
                        if order_id_str:
                            all_cell_updates.append(gspread.Cell(current_row, order_id_idx_2, order_id_str))
                        if order_name_str:
                            all_cell_updates.append(gspread.Cell(current_row, order_name_idx_2, order_name_str))
                        if trafficker_str:
                            all_cell_updates.append(gspread.Cell(current_row, trafficker_idx_2, trafficker_str))
                        if creator_str:
                            all_cell_updates.append(gspread.Cell(current_row, creator_idx_2, creator_str))
                    else:
                        print(f"[WARNING] Unknown client network: {client_network}")
                    
                    print(f"[INFO] Prepared updates for row {current_row} with order: {order_name_str} (Client: {client_network}), geo included: {geo_included_str}, geo excluded: {geo_excluded_str}, order ID: {order_id_str}, trafficker: {trafficker_str}, creator: {creator_str}")
                
                # Batch update all cells for this campaign
                if all_cell_updates:
                    try:
                        ws.update_cells(all_cell_updates)
                        print(f"[INFO] Successfully updated {len(all_cell_updates)} cells for campaign: {campaign_name}")
                        # Rate limiting after batch update
                        time.sleep(2.0)
                    except Exception as e:
                        print(f"[ERROR] Failed to batch update cells for campaign {campaign_name}: {e}")
                        # Fallback to individual updates if batch fails
                        for cell in all_cell_updates:
                            try:
                                ws.update_cell(cell.row, cell.col, cell.value)
                                time.sleep(0.5)
                            except Exception as cell_error:
                                print(f"[ERROR] Failed to update cell ({cell.row}, {cell.col}): {cell_error}")
            
        except Exception as e:
            print(f"[ERROR] Processing row {i}: {e}")
            continue
    
    print(f"[DONE] Completed processing sheet: {ws.title}")

def main():
    """Main function to run the script"""
    print("[INFO] Starting GAM Geo Fetch Script - INCREMENTAL UPDATE MODE")
    print("[INFO] This script will only update rows with missing geo data, enabling hourly cron efficiency")
    
    # Setup Google Sheets
    gc = setup_google_sheets()
    if not gc:
        print("[ERROR] Failed to setup Google Sheets. Exiting.")
        return
    
    # Initialize GAM clients
    clients = []
    for yaml_file in GAM_YAMLS:
        try:
            if os.path.exists(yaml_file):
                client = ad_manager.AdManagerClient.LoadFromStorage(yaml_file)
                clients.append(client)
                print(f"[INFO] Successfully loaded GAM client from {yaml_file}")
            else:
                print(f"[WARNING] YAML file not found: {yaml_file}")
        except Exception as e:
            print(f"[ERROR] Error loading GAM client from {yaml_file}: {e}")
    
    if not clients:
        print("[ERROR] No GAM clients loaded. Cannot proceed.")
        return
    
    # Open the spreadsheet
    try:
        sh = gc.open_by_key(SHEET_ID)
        print(f"[INFO] Successfully connected to Google Sheet: {sh.title}")
    except Exception as e:
        print(f"[ERROR] Failed to open Google Sheet: {e}")
        return
    
    # Find sheets that need updating
    sheets_to_update = find_sheets_to_update(sh)
    if not sheets_to_update:
        print("[INFO] No sheets need updating. All data appears to be filled.")
        print("[INFO] This is expected behavior for incremental updates - only missing data will be filled.")
        return
    
    print(f"[INFO] Found {len(sheets_to_update)} sheets that need updating")
    
    # Track progress for this run
    total_sheets_processed = 0
    total_rows_updated = 0
    start_time = datetime.now()
    
    # Process all sheets that need updating
    for ws in sheets_to_update:
        print(f"\n[INFO] Processing sheet: {ws.title}")
        rows_needing_update = get_rows_needing_update(ws)
        total_rows_updated += len(rows_needing_update)
        total_sheets_processed += 1
        
        print(f"[INFO] Found {len(rows_needing_update)} rows needing update in sheet {ws.title}")
        process_sheet(ws)
    
    # Calculate run statistics
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n[DONE] All sheets processed successfully!")
    print(f"[SUMMARY] Run completed in {duration.total_seconds():.1f} seconds")
    print(f"[SUMMARY] Sheets processed: {total_sheets_processed}")
    print(f"[SUMMARY] Total rows updated: {total_rows_updated}")
    print(f"[SUMMARY] Incremental update complete - only missing data was filled")
    print(f"[INFO] Next hourly run will continue filling any remaining empty rows")

if __name__ == "__main__":
    main() 