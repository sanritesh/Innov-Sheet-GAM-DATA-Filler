# 🔍 Order & Line Item Filtering Changes

##  **New Filtering Rules Applied**

### **1. Order Status Filtering** 

#### **Excluded Order Status:**
- **COMPLETED**: Orders with status 'COMPLETED' are automatically excluded
- **Reason**: Completed orders are no longer active and shouldn't be processed

#### **Implementation:**
```python
def is_valid_order(order):
    # Check if order status is not COMPLETED
    order_status = getattr(order, 'status', '')
    if order_status == 'COMPLETED':
        print(f"[DEBUG] Skipping order with COMPLETED status")
        return False
```

### **2. Line Item Status Filtering** 

#### **Excluded Line Item Status:**
- **COMPLETED**: Line items with status 'COMPLETED' are automatically excluded
- **Reason**: Completed line items are no longer active and shouldn't be processed

#### **Implementation:**
```python
def is_active_sponsorship(li):
    # Check if line item status is not COMPLETED
    line_item_status = getattr(li, 'lineItemType', '')
    if line_item_status == 'COMPLETED':
        print(f"[DEBUG] Skipping line item with COMPLETED status")
        return False
```

### **3. Date-Based Filtering** 

#### **Date Range Filters:**
- **Past Date Range**: Exclude orders/line items where BOTH start AND end dates are before current date
- **Current/Past Date Range**: Exclude orders/line items where BOTH start AND end dates are current date or earlier
- **Multi-day CPD Campaigns**: Include orders/line items where end date is T+1 or greater (even if start date is past/current)
- **Future End Dates**: Include if end date extends beyond current date

#### **Implementation:**
```python
# Get current date and date ranges
current_date = now.date()
start_date_only = start_dt.date()
end_date_only = end_dt.date()

# Filter 1: Exclude if both start and end dates are in the past
if start_date_only < current_date and end_date_only < current_date:
    print(f"[DEBUG] Skipping line item with past date range: start={start_date_only}, end={end_date_only} < {current_date}")
    return False

# Filter 2: Exclude if both start and end dates are current date or earlier
if start_date_only <= current_date and end_date_only <= current_date:
    print(f"[DEBUG] Skipping line item with current/past date range: start={start_date_only}, end={end_date_only} <= {current_date}")
    return False

# Filter 3: Include if end date is T+1 or greater (multi-day CPD campaign)
if end_date_only > current_date:
    print(f"[DEBUG] Including line item with future end date: start={start_date_only}, end={end_date_only} > {current_date}")
    return True
```

##  **Filtering Logic Summary**

### **What Gets Excluded:**
1. **Completed Orders**: `status == 'COMPLETED'`
2. **Completed Line Items**: `status == 'COMPLETED'`
3. **Past Date Range**: `start_date < current_date AND end_date < current_date`
4. **Current/Past Date Range**: `start_date <= current_date AND end_date <= current_date`

### **What Gets Included:**
1. **Active Orders**: `status != 'COMPLETED'`
2. **Active Line Items**: `status != 'COMPLETED'`
3. **Multi-day CPD Campaigns**: `end_date > current_date` (even if start_date is past/current)
4. **SPONSORSHIP Type**: `lineItemType == 'SPONSORSHIP'`

## **Filtering Applied At:**

### **1. Order Level:**
- When searching for orders by campaign name
- When retrieving order details for line items
- Before processing order information

### **2. Line Item Level:**
- When checking if line item is active sponsorship
- When processing line items from orders
- When doing direct line item searches

##  **Debug Output Examples:**

### **Excluded Orders:**
```
[DEBUG] Skipping order with COMPLETED status
[DEBUG] Skipping order with past date range: start=2025-07-05, end=2025-07-08 < 2025-07-10
[DEBUG] Skipping order with current/past date range: start=2025-07-10, end=2025-07-10 <= 2025-07-10
```

### **Excluded Line Items:**
```
[DEBUG] Skipping line item with COMPLETED status
[DEBUG] Skipping line item with past date range: start=2025-07-05, end=2025-07-08 < 2025-07-10
[DEBUG] Skipping line item with current/past date range: start=2025-07-10, end=2025-07-10 <= 2025-07-10
```

### **Included Items:**
```
[DEBUG] Including order with future end date: start=2025-07-08, end=2025-07-15 > 2025-07-10
[DEBUG] Including line item with future end date: start=2025-07-05, end=2025-07-12 > 2025-07-10
[DEBUG] Found valid order: Campaign XYZ (ID: 12345)
[DEBUG] Line item is active and of type SPONSORSHIP
```

## **Benefits of New Filtering:**

### **Data Quality:**
- **Accurate Data**: Only processes active, future campaigns
- **Relevant Results**: Excludes completed and past campaigns
- **Clean Output**: No outdated or irrelevant information

### **Performance:**
- **Faster Processing**: Fewer items to process
- **Reduced API Calls**: Excludes invalid items early
- **Better Cache Usage**: More relevant cached results

### **Business Logic:**
- **Multi-day CPD Support**: Properly handles campaigns spanning multiple days
- **Active Campaigns**: Only processes non-completed campaigns
- **Smart Date Filtering**: Considers both start and end dates for relevance
- **Future-Relevant**: Includes campaigns with future end dates

## 🔧 **Technical Implementation:**

### **Order Validation Function:**
```python
def is_valid_order(order):
    """Check if order is valid (not completed and has future start date)"""
    # Check order status
    # Check start date
    # Return True/False
```

### **Line Item Validation Function:**
```python
def is_active_sponsorship(li):
    """Check if line item is active sponsorship with future start date"""
    # Check line item type
    # Check line item status
    # Check start date
    # Return True/False
```

### **Integration Points:**
1. **Order Search**: Applied when finding orders by campaign name
2. **Line Item Search**: Applied when doing direct line item searches
3. **Order Retrieval**: Applied when getting order details for line items

##  **Expected Impact:**

### **Before Filtering:**
- Processed all orders/line items found
- Included completed campaigns
- Included past campaigns
- Mixed current and future campaigns
- Didn't properly handle multi-day CPD campaigns

### **After Filtering:**
- Only processes active campaigns
- Excludes completed campaigns
- Excludes campaigns where both start and end dates are in the past
- Includes multi-day CPD campaigns with future end dates
- Smart date range filtering for better relevance

## **Deployment Notes:**

### **Testing:**
- Verify that completed orders are excluded
- Verify that past date orders are excluded
- Verify that current date orders are excluded
- Verify that future date orders are included

### **Monitoring:**
- Check debug logs for filtering messages
- Monitor processing time improvements
- Verify data quality improvements
- Track any unexpected exclusions

### **Rollback:**
- Can easily remove filtering functions if needed
- Debug logs will show what was excluded
- Original logic still available in code 