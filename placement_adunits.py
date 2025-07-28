import asyncio
from quart import Quart, jsonify, request
from googleads import ad_manager
from datetime import datetime, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account

import sys
import io

# Force stdout and stderr to use UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = Quart(__name__)

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SAMPLE_SPREADSHEET_ID = '1x_kgiq6LYwycKYd-nmR3TdD8Mf0bCm-o_jToamjlpG4'

# Add caching for geo mappings at the top level
geo_cache = {}
ad_unit_cache = {}
placement_cache = {}

# Add rate limiting
from collections import defaultdict
import time

# Rate limiting storage
request_counts = defaultdict(list)
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX_REQUESTS = 100  # Max requests per hour per IP

def get_geo_mapping(sheet_name="Country"):
    """Fetch geo mapping data from a specific sheet in Google Sheets, with caching."""
    if sheet_name in geo_cache:
        return geo_cache[sheet_name]
    try:
        print(f"\n[DEBUG] Fetching geo mapping for {sheet_name}")
        credentials = service_account.Credentials.from_service_account_file(
            'til-adquality-project-71546b9ff5d8.json',
            scopes=SCOPES
        )
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(SAMPLE_SPREADSHEET_ID).worksheet(sheet_name)
        values = sheet.get_all_records()
        if not values:
            print(f"No data found in {sheet_name} sheet.")
            geo_cache[sheet_name] = {}
            return {}
        id_key = [k for k in values[0].keys() if 'ID' in k.upper()][0]
        name_key = [k for k in values[0].keys() if k.lower() in ['country', 'state', 'city', 'region']][0]
        geo_mapping = {str(row[id_key]): row[name_key] for row in values if id_key in row and name_key in row}
        print(f"[DEBUG] Loaded {len(geo_mapping)} mappings for {sheet_name}")
        geo_cache[sheet_name] = geo_mapping
        return geo_mapping
    except Exception as e:
        print(f"Error fetching geo mapping from {sheet_name}: {str(e)}")
        import traceback
        print(f"[DEBUG] Full error traceback: {traceback.format_exc()}")
        geo_cache[sheet_name] = {}
        return {}

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

async def fetch_ad_units_for_placement(client, placement_id):
    """Fetch ad units for a placement with improved caching."""
    global ad_unit_cache
    
    # Check if we already have the ad units for this placement
    if placement_id in ad_unit_cache:
        return ad_unit_cache[placement_id]
    
    try:
        # Create statement to select ad units
        statement = {
            'query': f'WHERE placementId = {placement_id}',
            'values': []
        }
        
        # Get ad units
        response = client.GetService('PlacementService').getAdUnitsByStatement(statement)
        
        if 'results' in response and response['results']:
            ad_units = response['results']
            # Cache the results
            ad_unit_cache[placement_id] = ad_units
            return ad_units
        return []
        
    except Exception as e:
        print(f"Error fetching ad units for placement {placement_id}: {str(e)}")
        return []

async def fetch_placement_names_in_batches(client, placement_ids):
    """Fetch placement names in optimized batches."""
    if not placement_ids:
        return {}
    
    # Check cache first
    uncached_ids = [id for id in placement_ids if str(id) not in placement_cache]
    if not uncached_ids:
        return {str(id): placement_cache[str(id)] for id in placement_ids}
    
    placement_names = {str(id): placement_cache[str(id)] for id in placement_ids if str(id) in placement_cache}
    batch_Template = 100  # Increased batch Template for better performance
    
    # Process in batches
    for i in range(0, len(uncached_ids), batch_Template):
        batch = list(uncached_ids)[i:i + batch_Template]
        try:
            statement = (ad_manager.StatementBuilder(version='v202411')
                        .Where('id IN ({})'.format(', '.join(map(str, batch)))))
            
            placement_service = client.GetService('PlacementService', version='v202411')
            response = placement_service.getPlacementsByStatement(statement.ToStatement())
            
            if hasattr(response, 'results') and response.results:
                for placement in response.results:
                    placement_names[str(placement.id)] = placement.name
                    placement_cache[str(placement.id)] = placement.name
                    
        except Exception as e:
            print(f"Error fetching batch of placements: {str(e)}")
            continue
            
    return placement_names

def deduce_platform_publisher_section_position(ad_unit_name):
    """Deduce publisher, platform, section, template, position, and position2 from Ad Unit name.
    
    Expected format: PUBLISHER_PLATFORM_SECTION_TEMPLATE_POSITION_POSITION2
    Example: ET_MWEB_AUTO_AS_ATF_P1 → ('ET', 'MWEB', 'AUTO', 'AS', 'ATF', 'P1')
    
    Args:
        ad_unit_name (str): The name of the ad unit
        
    Returns:
        tuple: (publisher, platform, section, template, position, position2)
    """
    # Default values
    defaults = ("unknown", "unknown", "unknown", "unknown", "unknown", "unknown")
    
    if not ad_unit_name or not isinstance(ad_unit_name, str):
        return defaults
        
    parts = ad_unit_name.split('_')
    if len(parts) < 2:
        return defaults
        
    # Extract parts with fallbacks
    publisher = parts[0].upper() if len(parts) > 0 else "unknown"
    platform = parts[1].upper() if len(parts) > 1 else "unknown"
    section = parts[2].upper() if len(parts) > 2 else "unknown"
    template = parts[3].upper() if len(parts) > 3 else "unknown"
    position = parts[4].upper() if len(parts) > 4 else "unknown"
    position2 = parts[5].upper() if len(parts) > 5 else "unknown"
    
    # Special handling for section if needed
    if section in {"AX", "ACROSS", "AX_ACROSS"}:
        section = "ROS"
    
    return publisher, platform, section, template, position, position2

def get_geo_targeting_details(targeting):
    """Extract geographic targeting details with improved error handling and name resolution."""
    geo_details = {"included": [], "excluded": []}
    try:
        # Fetch all mappings
        country_mapping = get_geo_mapping("Country")
        state_mapping = get_geo_mapping("States")
        city_mapping = get_geo_mapping("City")

        print(f"\n[DEBUG] Geo mappings loaded:")
        print(f"Country mapping: {country_mapping}")
        print(f"State mapping: {state_mapping}")
        print(f"City mapping: {city_mapping}")

        def resolve_geo_name(location_id, location_type, default_name):
            """Resolve location name from mapping with improved accuracy."""
            if location_type.lower() == "country":
                return country_mapping.get(str(location_id), default_name)
            elif location_type.lower() == "state":
                return state_mapping.get(str(location_id), default_name)
            elif location_type.lower() == "city":
                return city_mapping.get(str(location_id), default_name)
            return default_name

        def is_valid_location(location):
            """Check if location is valid and has a proper name."""
            if not location:
                return False
                
            location_id = str(getattr(location, 'id', None))
            location_name = getattr(location, 'displayName', 'Unknown')
            location_type = getattr(location, 'type', 'Unknown')
            
            # Accept CITY, STATE, COUNTRY, UNION_TERRITORY, DEPARTMENT & SUB_DISTRICT types
            valid_types = ['CITY', 'STATE', 'COUNTRY', 'UNION_TERRITORY', 'DEPARTMENT', 'SUB_DISTRICT']
            if location_type not in valid_types:
                print(f"[DEBUG] Skipping location with invalid type: {location_type}")
                return False
                
            # Skip if we can't resolve the name from our mappings
            resolved_name = resolve_geo_name(location_id, location_type, location_name)
            if resolved_name == 'Unknown':
                print(f"[DEBUG] Could not resolve name for location: {location_name}")
                return False
                
            return True

        print(f"\n[DEBUG] Processing geo targeting for line item")
        print(f"[DEBUG] Targeting object: {targeting}")
        
        if hasattr(targeting, 'geoTargeting'):
            print(f"[DEBUG] Found geoTargeting attribute")
            geoTargeting = targeting.geoTargeting
            
            # Included locations
            if hasattr(geoTargeting, 'targetedLocations'):
                print(f"[DEBUG] Processing included locations")
                for location in geoTargeting.targetedLocations:
                    print(f"[DEBUG] Processing location: {location}")
                    if not is_valid_location(location):
                        print(f"[DEBUG] Skipping invalid location: {location}")
                        continue
                        
                    location_id = str(getattr(location, 'id', None))
                    location_name = getattr(location, 'displayName', 'Unknown')
                    location_type = getattr(location, 'type', 'Unknown')
                    mapped_name = resolve_geo_name(location_id, location_type, location_name)
                    
                    geo_details["included"].append({
                        "id": location_id,
                        "name": mapped_name,
                        "type": location_type
                    })
                    print(f"[DEBUG] Added included location: {mapped_name}")
            
            # Excluded locations
            if hasattr(geoTargeting, 'excludedLocations'):
                print(f"[DEBUG] Processing excluded locations")
                for location in geoTargeting.excludedLocations:
                    print(f"[DEBUG] Processing location: {location}")
                    if not is_valid_location(location):
                        print(f"[DEBUG] Skipping invalid location: {location}")
                        continue
                        
                    location_id = str(getattr(location, 'id', None))
                    location_name = getattr(location, 'displayName', 'Unknown')
                    location_type = getattr(location, 'type', 'Unknown')
                    mapped_name = resolve_geo_name(location_id, location_type, location_name)
                    
                    geo_details["excluded"].append({
                        "id": location_id,
                        "name": mapped_name,
                        "type": location_type
                    })
                    print(f"[DEBUG] Added excluded location: {mapped_name}")
                    
            # Sort locations by name for consistency
            geo_details["included"].sort(key=lambda x: x["name"])
            geo_details["excluded"].sort(key=lambda x: x["name"])
            
            print(f"[DEBUG] Final geo details: {geo_details}")
            
    except Exception as e:
        print(f"Error extracting geo targeting: {str(e)}")
        import traceback
        print(f"[DEBUG] Full error traceback: {traceback.format_exc()}")
        
    if not geo_details["included"] and not geo_details["excluded"]:
        return None
    return geo_details

def get_targeting_details(client, targeting, ad_unit_names_cache, placement_names_cache):
    """Extract targeting details including geo targeting with better structure."""
    targeting_details = {
        "ad_units": [],
        "placements": [],
        "geo": None
    }

    try:
        print("\n[DEBUG] Processing targeting details")
        # Inventory targeting
        if hasattr(targeting, 'inventoryTargeting') and targeting.inventoryTargeting:
            inventory_targeting = targeting.inventoryTargeting
            print(f"[DEBUG] Found inventory targeting")
            
            # Process ad unit targeting
            if hasattr(inventory_targeting, 'targetedAdUnits'):
                print(f"[DEBUG] Processing ad unit targeting")
                for ad_unit in inventory_targeting.targetedAdUnits:
                    ad_unit_id = getattr(ad_unit, 'adUnitId', None)
                    if ad_unit_id is not None:
                        print(f"[DEBUG] Processing ad unit ID: {ad_unit_id}")
                        ad_unit_name = ad_unit_names_cache.get(str(ad_unit_id), "Unknown")
                        publisher, platform, section, Template, size = deduce_platform_publisher_section_position(ad_unit_name)
                        print(f"[DEBUG] Ad Unit: {ad_unit_name} -> Platform: {platform}, Publisher: {publisher}, Section: {section}, Template: {Template}, Position: {size}")
                        targeting_details["ad_units"].append({
                            "id": str(ad_unit_id),
                            "name": ad_unit_name,
                            "platform": platform,
                            "publisher": publisher,
                            "section": section,
                            "Template": Template,
                            "size": size
                        })
            
            # Process placement targeting
            if hasattr(inventory_targeting, 'targetedPlacements'):
                print(f"[DEBUG] Processing placement targeting")
                for placement in inventory_targeting.targetedPlacements:
                    placement_id = getattr(placement, 'placementId', None)
                    if placement_id is not None:
                        print(f"[DEBUG] Processing placement ID: {placement_id}")
                        placement_info = placement_names_cache.get(str(placement_id), {
                            'name': 'Unknown',
                            'description': '',
                            'ad_units': []
                        })
                        print(f"[DEBUG] Placement: {placement_info['name']}")
                        
                        # Add placement to targeting details
                        targeting_details["placements"].append({
                            "id": str(placement_id),
                            "name": placement_info['name'],
                            "description": placement_info['description']
                        })
                        
                        # Add ad units from placement to targeting details
                        for ad_unit in placement_info.get('ad_units', []):
                            ad_unit_id = str(ad_unit.get('id'))
                            ad_unit_name = ad_unit.get('name', 'Unknown')
                            publisher, platform, section, Template, size = deduce_platform_publisher_section_position(ad_unit_name)
                            print(f"[DEBUG] Ad Unit from placement: {ad_unit_name} -> Platform: {platform}, Publisher: {publisher}, Section: {section}, Template: {Template}, Position: {size}")
                            targeting_details["ad_units"].append({
                                "id": ad_unit_id,
                                "name": ad_unit_name,
                                "platform": platform,
                                "publisher": publisher,
                                "section": section,
                                "Template": Template,
                                "size": size
                            })

        # Geo targeting
        geo_data = get_geo_targeting_details(targeting)
        if geo_data:
            targeting_details["geo"] = geo_data

        print(f"[DEBUG] Final targeting details:")
        print(f"Ad Units: {targeting_details['ad_units']}")
        print(f"Placements: {targeting_details['placements']}")
        print(f"Geo: {targeting_details['geo']}")

    except Exception as e:
        print(f"[DEBUG] Error in get_targeting_details: {str(e)}")
        targeting_details["error"] = f"Error extracting targeting details: {str(e)}"

    return targeting_details

def transform_to_desired_structure(sponsorships, placement_adunit_map=None, include_line_items=False):
    """Transform data into a publisher-based structure with platforms, sections, templates, positions, and geo targeting.
    
    Args:
        sponsorships: List of sponsorship objects
        placement_adunit_map: Mapping of placement IDs to ad units
        include_line_items: Whether to include line_items field in the output (default: False)
    """
    result = {"publishers": {}}
    if placement_adunit_map is None:
        placement_adunit_map = {}

    def normalize_position(pos):
        """Normalize position names for both position and position2 fields."""
        if not pos or not isinstance(pos, str):
            return 'unknown'
            
        pos = pos.upper()
        position_mapping = { 
            'ATF': 'ATF',     
            'BTF': 'BTF',            
            'MREC': 'MREC',
            'BO': 'BO',              
            'RHS': 'RHS',    
            'BOTTOMOVERLAY': 'BO',
            'TOPBANNER': 'TB',
            'LEADERBOARD': 'LB',
            'SKIN': 'SKIN',
            'INTERSTITIAL': 'INT',
            'MTF': 'MTF',
            'LB': 'LB',
            'CUBE': 'CUBE',
            'BTFMREC': 'BTFMREC'
        }
        return position_mapping.get(pos, pos.lower())

    def get_publisher_from_name(name):
        name = name.upper()
        if '_ET_' in name or name.startswith('ET_'):
            return 'ET'
        elif '_TOI_' in name or name.startswith('TOI_'):
            return 'TOI'
        elif '_ETIMES_' in name or name.startswith('ETIMES_'):
            return 'ETIMES'
        elif '_NEWSPOINT_' in name or name.startswith('NEWSPOINT_'):
            return 'NEWSPOINT'
        elif '_NBT_' in name or name.startswith('NBT_'):
            return 'NBT'
        elif '_IAG_' in name or name.startswith('IAG_'):
            return 'IAG'
        elif '_TLG_' in name or name.startswith('TLG_'):
            return 'TLG'
        elif '_MT_' in name or name.startswith('MT_'):
            return 'MT'
        elif '_VK_' in name or name.startswith('VK_'):
            return 'VK'
        elif '_MS_' in name or name.startswith('MS_'):
            return 'MS'
        elif '_TML_' in name or name.startswith('TML_'):
            return 'TML'
        elif '_ITBANGLA_' in name or name.startswith('ITBANGLA_'):
            return 'ITBANGLA'
        elif '_ALL_LANGUAGES_' in name or name.startswith('ALL_LANGUAGES_'):
            return 'ALL_LANGUAGES'
        elif '_ETMALAYALAM_' in name or name.startswith('ETMALAYALAM_'):
            return 'ET_MALAYALAM'
        elif '_ETHINDI_' in name or name.startswith('ETHINDI_'):
            return 'ET_HINDI'
        elif '_ETMARATHI_' in name or name.startswith('ETMARATHI_'):
            return 'ET_MARATHI'
        elif '_ETBENGALI_' in name or name.startswith('ETBENGALI_'):
            return 'ET_BENGALI'
        elif '_ETKANNADA_' in name or name.startswith('ETKANNADA_'):
            return 'ET_KANNADA'
        elif '_ETTAMIL_' in name or name.startswith('ETTAMIL_'):
            return 'ET_TAMIL'
        elif '_ETTELUGU_' in name or name.startswith('ETTELUGU_'):
            return 'ET_TELUGU'
        elif '_ETGUJARATI_' in name or name.startswith('ETGUJARATI_'):
            return 'ET_GUJARATI'
        return 'unknown'

    def get_section_from_name(name):
        """Get section from name with updated section mappings."""
        name = name.upper()
        sections = {
            'HOME': 'home',
            'NEWS': 'news',
            'MARKET': 'market',
            'WEALTH': 'wealth',
            'SPORTS': 'sports',
            'POLITICS': 'politics',
            'INDIA': 'india',
            'INTERNATIONAL': 'international',
            'STOCK': 'stock',
            'BANKING': 'banking',
            'TAX': 'tax',
            'REALESTATE': 'realestate',
            'TRANSPORTATION': 'transportation',
            'HEALTHCARE': 'healthcare',
            'CALCULATORS': 'calculators',
            'INDLGOODS': 'indlgoods',
            'CITY': 'city',
            'WORLD': 'world',
            'PANACHE': 'panache',
            'EXPERTVIEW': 'expertview',
            'RISE': 'rise',
            'NRI': 'nri',
            'BONDS': 'bonds',
            'CONSPRODUCTS': 'consproducts',
            'INSURE': 'insure',
            'MARKETDATA': 'marketdata',
            'MARKETSTATS': 'marketstats',
            'ACROSS': 'ros',
            'AX': 'ros',
            'AX_ACROSS': 'ros',
            'ASTROLOGY': 'ASTRO',
            'VIRAL': 'VIRAL',
            'TV': 'TV',

            'AUTO': 'AUTO',
            'BORROW': 'BORROW',
            'BUDGET': 'BUDGET',
            'CAREERS': 'CAREERS',
            'COMMODITIES': 'COMMODITIES',
            'CRYPTO': 'CRYPTO',
            'EARN': 'EARN',
            'ELECTIONS': 'ELECTIONS',
            'ELECTION': 'ELECTION',
            'ENERGY':'ENERGY',
            'ENTERTAINMENT': 'ENTERTAINMENT',
            'FOREX': 'FOREX',
            'INDICES': 'INDICES',
            'INDUSTRY': 'INDUSTRY',
            'IPO': 'IPO',
            'LEGAL': 'LEGAL',
            'LUXURY': 'LUXURY',
            'MEDIA': 'MEDIA',
            'MF': 'MF',
            'OPINION': 'OPINION',
            'OTHERS': 'OTHERS',
            'PLAN': 'PLAN',
            'PRIME': 'PRIME',
            'RENEWABLES': 'RENEWABLES',
            'SAVE': 'SAVE',
            'SERVICES': 'SERVICES',
            'SPEND': 'SPEND',
            'TECHNICALCHART': 'TECHNICALCHART',
            'TECHNOLOGY': 'TECHNOLOGY',
            'TELECOM': 'TELECOM',
            'EDUCATION': 'EDUCATION',
            'INVEST': 'invest',
            'BUSINESS': 'BUSINESS',
            'INDIA':'INDIA',
            'CRICKET': 'CRICKET',
            'PHOTOGALLERY': 'PHOTOGALLERY',
            'SPORTS': 'SPORTS',
            'PSBK': 'Colombia_Passback',
            'ADSHIELD': 'ADSHIELD',
            'ENTERTAINMENT': 'ENTERTAINMENT',
            'FITNESS':'FITNESS',
            'FOODNEWS':'FOODNEWS',
            'LIFESTYLE':'LIFESTYLE',
            'OTHERS':'OTHERS',
            'PARENTING':'PARENTING',
            'RECIPES':'RECIPES',
            'RELATIONSHIPS':'RELATIONSHIPS',
            'TRAVEL':'TRAVEL',
            'TV':'TV',
            'WEBSERIES':'WEBSERIES',
            'VIVOBROWSER': 'VIVOBROWSER',
            'VIVOLOCK': 'VIVOLOCK',
            'OPPOBROWSER': 'OPPOBROWSER',
            'XIAOMIBROWSER': 'XIAOMIBROWSER',
            'JIO':'JIO',
            'AFMOBIBROWSER': 'AFMOBIBROWSER',
            'PWA': 'PWA',
            'HEALTH': 'HEALTH',
            'FASHION': 'FASHION',
            'NEWS': 'NEWS',
            'SPEAKINGTREE': 'SPEAKINGTREE',
            'MICROSITE': 'MICROSITE',
            'GOVERNMENT': 'GOVERNMENT',
            'IPL': 'IPL'
        }
        
        # Check if any section appears in the name
        for section in sections:
            if f'_{section}_' in name or name.startswith(f'{section}_'):
                return sections[section]
        
        return 'unknown'

    # Process all sponsorships and collect position-based data
    for sponsorship in sponsorships:
        if not isinstance(sponsorship, dict):
            continue
            
        line_item_name = sponsorship.get('name', 'Unknown')
        print(f"\n[DEBUG] Processing Line Item: {line_item_name}")
        
        # Get geo targeting for this sponsorship
        geo_targeting = None
        if 'targeting' in sponsorship and 'geo' in sponsorship['targeting']:
            geo_targeting = sponsorship['targeting']['geo']

        # --- Collect all ad units: direct + from placements ---
        ad_units = set()
        
        # Direct ad units
        direct_ad_units = sponsorship.get('ad_units', [])
        print(f"[DEBUG] Found {len(direct_ad_units)} direct ad units for {line_item_name}")
        for ad_unit in direct_ad_units:
            ad_unit_name = ad_unit.get('name', '')
            if ad_unit_name:
                ad_units.add(ad_unit_name)
                print(f"[DEBUG] Added direct ad unit: {ad_unit_name}")
            else:
                print(f"[DEBUG] Skipping direct ad unit with no name: {ad_unit}")
        
        # Ad units from placements
        placements = sponsorship.get('placements', [])
        print(f"[DEBUG] Found {len(placements)} placements for {line_item_name}")
        for placement in placements:
            placement_id = placement.get('id')
            if not placement_id:
                print(f"[DEBUG] Skipping placement with no ID: {placement}")
                continue
                
            placement_id_str = str(placement_id)
            if placement_id_str not in placement_adunit_map:
                print(f"[DEBUG] Placement ID {placement_id_str} not found in placement_adunit_map")
                continue
                
            placement_ad_units = placement_adunit_map[placement_id_str]
            print(f"[DEBUG] Found {len(placement_ad_units)} ad units in placement {placement_id_str}")
            
            for ad_unit in placement_ad_units:
                ad_unit_name = ad_unit.get('name', '')
                if ad_unit_name:
                    ad_units.add(ad_unit_name)
                    print(f"[DEBUG] Added ad unit from placement {placement_id_str}: {ad_unit_name}")
                else:
                    print(f"[DEBUG] Skipping ad unit with no name in placement {placement_id_str}: {ad_unit}")
        
        print(f"[DEBUG] Total unique ad units for {line_item_name}: {len(ad_units)}")

        # --- Process all ad units and create publisher-based structure ---
        for ad_unit_name in ad_units:
            publisher, platform, section, template, position, position2 = deduce_platform_publisher_section_position(ad_unit_name)
            detected_publisher = get_publisher_from_name(ad_unit_name)
            publisher = detected_publisher or publisher
            section = get_section_from_name(ad_unit_name) or section
            
            # Debug logging for publisher detection
            if detected_publisher and detected_publisher not in ['ET', 'ET_BENGALI', 'ET_GUJARATI', 'ET_HINDI', 'ET_KANNADA', 'ET_MALAYALAM', 'ET_MARATHI', 'ET_TAMIL', 'ET_TELUGU']:
                print(f"[DEBUG] Found non-ET publisher: {detected_publisher} from ad unit: {ad_unit_name}")
            elif detected_publisher == 'unknown':
                print(f"[DEBUG] Could not detect publisher for ad unit: {ad_unit_name}")
            
            # Normalize all keys to upper for consistency
            publisher = publisher.upper() if publisher else 'UNKNOWN'
            platform = platform.upper() if platform else 'UNKNOWN'
            section = section.upper() if section else 'UNKNOWN'
            template = template.upper() if template else 'UNKNOWN'
            position = normalize_position(position)
            position2 = normalize_position(position2)
            
            if not publisher or not platform:
                continue
                
            # Initialize publisher if it doesn't exist
            if publisher not in result["publishers"]:
                result["publishers"][publisher] = {
                    "platforms": {}
                }
            
            # Initialize platform if it doesn't exist
            if platform not in result["publishers"][publisher]["platforms"]:
                result["publishers"][publisher]["platforms"][platform] = {
                    "sections": {}
                }
            
            # Initialize section if it doesn't exist
            if section not in result["publishers"][publisher]["platforms"][platform]["sections"]:
                result["publishers"][publisher]["platforms"][platform]["sections"][section] = {
                    "templates": set(),
                    "positions": set(),
                    "positions2": set(),
                    "geo": geo_targeting
                }
            
            # Add values to sets
            result["publishers"][publisher]["platforms"][platform]["sections"][section]["templates"].add(template)
            result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions"].add(position)
            result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions2"].add(position2)
            
            # Merge geo targeting if multiple line items target the same section
            if geo_targeting and result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]:
                existing_geo = result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]
                # Merge geo targeting (union of included, intersection of excluded)
                merged_geo = {
                    "included": list(set(
                        (loc["id"], loc["name"], loc["type"]) 
                        for loc in existing_geo.get("included", [])
                    ).union(set(
                        (loc["id"], loc["name"], loc["type"]) 
                        for loc in geo_targeting.get("included", [])
                    ))),
                    "excluded": list(set(
                        (loc["id"], loc["name"], loc["type"]) 
                        for loc in existing_geo.get("excluded", [])
                    ).intersection(set(
                        (loc["id"], loc["name"], loc["type"]) 
                        for loc in geo_targeting.get("excluded", [])
                    )))
                }
                # Convert back to dict format
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]["included"] = [
                    {"id": loc[0], "name": loc[1], "type": loc[2]} 
                    for loc in merged_geo["included"]
                ]
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]["excluded"] = [
                    {"id": loc[0], "name": loc[1], "type": loc[2]} 
                    for loc in merged_geo["excluded"]
                ]
            elif geo_targeting and not result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]:
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"] = geo_targeting

    # Convert sets to lists and clean up
    for publisher in result["publishers"]:
        for platform in result["publishers"][publisher]["platforms"]:
            for section in result["publishers"][publisher]["platforms"][platform]["sections"]:
                # Convert sets to sorted lists
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["templates"] = sorted(list(result["publishers"][publisher]["platforms"][platform]["sections"][section]["templates"]))
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions"] = sorted(list(result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions"]))
                result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions2"] = sorted(list(result["publishers"][publisher]["platforms"][platform]["sections"][section]["positions2"]))
                
                # Clean up empty geo targeting
                if not result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]:
                    del result["publishers"][publisher]["platforms"][platform]["sections"][section]["geo"]
            
    return result

async def fetch_ad_units_for_placements_in_batches(client, placement_ids):
    """Efficiently fetch ad units for given placements while retaining placement ID mappings."""
    if not placement_ids:
        return {}

    placement_service = client.GetService('PlacementService', version='v202411')
    inventory_service = client.GetService('InventoryService', version='v202411')
    placement_batch_Template = 100
    ad_unit_batch_Template = 500

    placement_adunit_ids_map = {}
    all_ad_unit_ids = set()

    print(f"\n[DEBUG] Fetching ad units for {len(placement_ids)} placements (optimized)")

    # Step 1: Fetch all targetedAdUnitIds from placements
    for i in range(0, len(placement_ids), placement_batch_Template):
        batch = placement_ids[i:i + placement_batch_Template]
        statement = (ad_manager.StatementBuilder(version='v202411')
                     .Where(f"id IN ({', '.join([f':p{idx}' for idx in range(len(batch))])})"))
        for idx, pid in enumerate(batch):
            statement = statement.WithBindVariable(f'p{idx}', int(pid))

        response = placement_service.getPlacementsByStatement(statement.ToStatement())
        if hasattr(response, 'results'):
            for placement in response.results:
                pid = str(getattr(placement, 'id', None))
                targeted_ids = getattr(placement, 'targetedAdUnitIds', [])
                if not pid:
                    print(f"[WARNING] Placement with missing ID encountered")
                    continue
                placement_adunit_ids_map[pid] = targeted_ids
                all_ad_unit_ids.update(targeted_ids)
                print(f"[DEBUG] Placement {pid} has {len(targeted_ids)} ad units".encode('utf-8', errors='replace').decode('utf-8'))

    print(f"[DEBUG] Total unique ad unit IDs to fetch: {len(all_ad_unit_ids)}")

    # Step 2: Fetch all ad unit details
    ad_unit_detail_map = {}
    ad_unit_list = list(all_ad_unit_ids)

    for i in range(0, len(ad_unit_list), ad_unit_batch_Template):
        batch = ad_unit_list[i:i + ad_unit_batch_Template]
        statement = (ad_manager.StatementBuilder(version='v202411')
                     .Where(f"id IN ({', '.join([f':a{idx}' for idx in range(len(batch))])})"))
        for idx, aid in enumerate(batch):
            statement = statement.WithBindVariable(f'a{idx}', aid)

        while True:
            response = inventory_service.getAdUnitsByStatement(statement.ToStatement())
            if not hasattr(response, 'results') or not response.results:
                break
            for ad_unit in response.results:
                ad_unit_detail_map[str(ad_unit.id)] = {
                    'id': str(ad_unit.id),
                    'name': ad_unit.name,
                    'adUnitCode': ad_unit.adUnitCode
                }
            statement.offset += statement.limit

    # Step 3: Build final placement → list of ad unit dicts
    placement_adunit_map = {}
    for pid, ad_ids in placement_adunit_ids_map.items():
        placement_adunit_map[pid] = [
            ad_unit_detail_map[str(aid)]
            for aid in ad_ids if str(aid) in ad_unit_detail_map
        ]
        print(f"[DEBUG] Placement {pid} → {len(placement_adunit_map[pid])} ad units")

    return placement_adunit_map


async def get_todays_sponsorships(client):
    """Get today's sponsorships with optimized API calls and caching."""
    try:
        # Set date range for today's sponsorships with timezone awareness
        tz = pytz.timezone('Asia/Kolkata')  # Using IST timezone
        today = datetime.now(tz)
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        print(f"[DEBUG] Date range: {start_date} to {end_date}")
        
        # Build statement for line items
        now = today
        statement = (ad_manager.StatementBuilder(version='v202411')
                    .Where("lineItemType = 'SPONSORSHIP' AND Status = 'Delivering' AND startDateTime <= :now AND endDateTime >= :now")
                    .WithBindVariable('now', now))
        
        # Get line items using LineItemService
        line_item_service = client.GetService('LineItemService', version='v202411')
        line_items = []
        while True:
            response = line_item_service.getLineItemsByStatement(statement.ToStatement())
            if hasattr(response, 'results') and response.results:
                line_items.extend(response.results)
                print(f"[DEBUG] Found {len(response.results)} line items in this batch")
                statement.offset += statement.limit
            else:
                break
        
        if not line_items:
            print("[DEBUG] No line items found for today.")
            return []
            
        print(f"[DEBUG] Total line items found: {len(line_items)}")
        for li in line_items:
            print(f"[DEBUG] Line Item: {li.name}")
        
        # Collect all ad unit IDs and placement IDs
        ad_unit_ids = set()
        placement_ids = set()
        for line_item in line_items:
            print(f"\n[DEBUG] Processing targeting for line item: {line_item.name}")
            if hasattr(line_item, 'targeting'):
                print(f"[DEBUG] Line item has targeting")
                if hasattr(line_item.targeting, 'inventoryTargeting'):
                    print(f"[DEBUG] Line item has inventory targeting")
                    print(f"[DEBUG] Inventory targeting structure: {line_item.targeting.inventoryTargeting}")
                    # Direct ad units
                    if hasattr(line_item.targeting.inventoryTargeting, 'targetedAdUnits'):
                        print(f"[DEBUG] Found {len(line_item.targeting.inventoryTargeting.targetedAdUnits)} direct ad units")
                        for ad_unit in line_item.targeting.inventoryTargeting.targetedAdUnits:
                            ad_unit_ids.add(ad_unit['adUnitId'])
                    
                    # Placements
                    if hasattr(line_item.targeting.inventoryTargeting, 'targetedPlacementIds'):
                        placement_ids_list = line_item.targeting.inventoryTargeting.targetedPlacementIds
                        print(f"[DEBUG] Found {len(placement_ids_list)} placement IDs in targetedPlacementIds for {line_item.name}")
                        for placement_id in placement_ids_list:
                            placement_ids.add(str(placement_id))
                            print(f"[DEBUG] Added placement ID from targetedPlacementIds: {placement_id}")
                    
                    if hasattr(line_item.targeting.inventoryTargeting, 'targetedPlacements'):
                        placements = line_item.targeting.inventoryTargeting.targetedPlacements
                        print(f"[DEBUG] Found {len(placements)} placements in targetedPlacements for {line_item.name}")
                        for placement in placements:
                            placement_id = None
                            if isinstance(placement, dict):
                                placement_id = placement.get('id') or placement.get('targetedPlacementId')
                                print(f"[DEBUG] Placement is dict, extracted id: {placement_id}")
                            elif isinstance(placement, (str, int)):
                                placement_id = placement
                                print(f"[DEBUG] Placement is {type(placement)}, using as id: {placement_id}")
                            else:
                                print(f"[DEBUG] Placement is unknown type: {type(placement)}")
                            if placement_id:
                                placement_ids.add(str(placement_id))
                                print(f"[DEBUG] Added placement ID from targetedPlacements: {placement_id}")
                    
                    print(f"[DEBUG] Current placement_ids set: {placement_ids}")
        
        print(f"\n[DEBUG] Total unique ad unit IDs: {len(ad_unit_ids)}")
        print(f"[DEBUG] Total unique placement IDs: {len(placement_ids)}")
        
        # Fetch ad unit and placement names in parallel
        ad_unit_names, placement_names = await asyncio.gather(
            fetch_ad_unit_names_in_batches(client, list(ad_unit_ids)),
            fetch_placement_names_in_batches(client, list(placement_ids))
        )
        
        print(f"\n[DEBUG] Fetched {len(ad_unit_names)} ad unit names")
        print(f"[DEBUG] Fetched {len(placement_names)} placement names")
        
        # Batch fetch ad units for all placements
        placement_adunit_map = await fetch_ad_units_for_placements_in_batches(client, list(placement_ids))
        print(f"\n[DEBUG] Fetched ad units for {len(placement_adunit_map)} placements".encode('ascii', errors='replace').decode('ascii'))
        
        # Process each line item
        processed_sponsorships = []
        for line_item in line_items:
            try:
                print(f"\n[DEBUG] Processing Line Item: {line_item.name}")
                
                # Extract geo targeting
                geo_targeting = None
                if hasattr(line_item, 'targeting') and hasattr(line_item.targeting, 'geoTargeting'):
                    print(f"[DEBUG] Found geo targeting for line item: {line_item.name}")
                    geo_targeting = get_geo_targeting_details(line_item.targeting)
                    print(f"[DEBUG] Extracted geo targeting: {geo_targeting}")
                
                # Extract ad units and placements
                ad_units = []
                placements = []
                if hasattr(line_item, 'targeting') and hasattr(line_item.targeting, 'inventoryTargeting'):
                    if hasattr(line_item.targeting.inventoryTargeting, 'targetedAdUnits'):
                        for ad_unit in line_item.targeting.inventoryTargeting.targetedAdUnits:
                            ad_unit_id = ad_unit['adUnitId']
                            if str(ad_unit_id) in ad_unit_names:
                                ad_units.append({
                                    'id': str(ad_unit_id),
                                    'name': ad_unit_names[str(ad_unit_id)]
                                })
                    if hasattr(line_item.targeting.inventoryTargeting, 'targetedPlacementIds'):
                        for placement_id in line_item.targeting.inventoryTargeting.targetedPlacementIds:
                            #placement_id = placement['id']
                            if str(placement_id) in placement_names:
                                placements.append({
                                    'id': str(placement_id),
                                    'name': placement_names[str(placement_id)]
                                })
                
                print(f"[DEBUG] Found {len(ad_units)} direct ad units and {len(placements)} placements for {line_item.name}")
                
                # Create sponsorship object
                sponsorship = {
                    'name': line_item.name,
                    'start_date': format_date_time(line_item.startDateTime),
                    'end_date': format_date_time(line_item.endDateTime),
                    'ad_units': ad_units,
                    'placements': placements,
                    'targeting': {
                        'geo': geo_targeting
                    }
                }
                processed_sponsorships.append(sponsorship)
                
            except Exception as e:
                print(f"Error processing line item {line_item.name}: {str(e)}")
                import traceback
                print(f"[DEBUG] Full error traceback: {traceback.format_exc()}")
                continue
        
        print(f"\n[DEBUG] Processed {len(processed_sponsorships)} sponsorships")
        
        # When calling transform_to_desired_structure, pass placement_adunit_map
        result = transform_to_desired_structure(processed_sponsorships, placement_adunit_map, include_line_items=False)
        print(f"\n[DEBUG] Final result has {len(result['publishers'])} publishers")
        return result
        
    except Exception as e:
        print(f"Error fetching today's sponsorships: {str(e)}")
        import traceback
        print(f"[DEBUG] Full error traceback: {traceback.format_exc()}")
        return []

async def fetch_ad_unit_names_in_batches(client, ad_unit_ids):
    """Fetch ad unit names in optimized batches."""
    if not ad_unit_ids:
        return {}
    
    # Check cache first
    uncached_ids = [id for id in ad_unit_ids if str(id) not in ad_unit_cache]
    if not uncached_ids:
        return {str(id): ad_unit_cache[str(id)] for id in ad_unit_ids}
    
    ad_unit_names = {str(id): ad_unit_cache[str(id)] for id in ad_unit_ids if str(id) in ad_unit_cache}
    batch_Template = 100  # Increased batch Template for better performance
    
    # Process in batches
    for i in range(0, len(uncached_ids), batch_Template):
        batch = list(uncached_ids)[i:i + batch_Template]
        try:
            statement = (ad_manager.StatementBuilder(version='v202411')
                        .Where('id IN ({})'.format(', '.join(map(str, batch)))))
            
            inventory_service = client.GetService('InventoryService', version='v202411')
            response = inventory_service.getAdUnitsByStatement(statement.ToStatement())
            
            if hasattr(response, 'results') and response.results:
                for ad_unit in response.results:
                    ad_unit_names[str(ad_unit.id)] = ad_unit.name
                    ad_unit_cache[str(ad_unit.id)] = ad_unit.name
                    
        except Exception as e:
            print(f"Error fetching batch of ad units: {str(e)}")
            continue
            
    return ad_unit_names

@app.route('/api/sponsorships', methods=['GET'])
async def sponsorships_api():
    """API endpoint to fetch position-based sponsorship data with geo targeting bound to each position."""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Clean old requests
        request_counts[client_ip] = [req_time for req_time in request_counts[client_ip] 
                                   if current_time - req_time < RATE_LIMIT_WINDOW]
        
        # Check rate limit
        if len(request_counts[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return jsonify({"message": "Rate limit exceeded", "status": "error"}), 429
        
        # Add current request
        request_counts[client_ip].append(current_time)
        
        # Simple API key authentication (optional)
        api_key = request.args.get('api_key')
        if api_key and api_key != 'your-secret-api-key-here':
            return jsonify({"message": "Invalid API key", "status": "error"}), 401
            
        # Clear caches periodically (every hour)
        current_time = datetime.now()
        if not hasattr(sponsorships_api, 'last_cache_clear') or \
           (current_time - sponsorships_api.last_cache_clear).total_seconds() > 3600:
            geo_cache.clear()
            ad_unit_cache.clear()
            placement_cache.clear()
            sponsorships_api.last_cache_clear = current_time
            
        client = ad_manager.AdManagerClient.LoadFromStorage('googleadsN.yaml')
        data = await get_todays_sponsorships(client)
        return jsonify({"data": data, "status": "success"})
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


