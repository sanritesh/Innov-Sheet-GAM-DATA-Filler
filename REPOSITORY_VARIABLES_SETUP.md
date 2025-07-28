# 🔧 Repository Variables Setup Guide

This guide will help you set up all the necessary repository variables for your GAM script in Bitbucket.

## 📋 Required Variables

Based on your `geofetchgsheet.py` script, you need the following variables:

### 1. **Google Sheets Configuration**
- `GOOGLE_SHEET_ID`: Your Google Sheet ID
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Service account credentials

### 2. **GAM Configuration**
- `GAM_YAML_FILES`: GAM YAML configuration files
- `GAM_NETWORK_CODES`: Network codes for GAM

### 3. **Exclusion Lists**
- `EXCLUDE_SUBSTRINGS`: Package names to exclude
- `EXCLUDE_PLATFORMS`: Platforms to exclude

---

## 🚀 Step-by-Step Setup

### Step 1: Access Repository Variables

1. Go to your Bitbucket repository
2. Navigate to **Repository settings** → **Pipelines** → **Repository variables**
3. Click **Add variable** for each variable below

### Step 2: Add Required Variables

#### 🔑 Google Sheets Variables

| Variable Name | Value | Secured |
|---------------|-------|---------|
| `GOOGLE_SHEET_ID` | `1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA` | ❌ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | `{"type": "service_account", ...}` | ✅ |

#### 🎯 GAM Variables

| Variable Name | Value | Secured |
|---------------|-------|---------|
| `GAM_NETWORK_CODES` | `7176,23037861279` | ❌ |
| `GAM_YAML_FILES` | `googleadsN.yaml,googleads.yaml` | ❌ |

#### 🚫 Exclusion Variables

| Variable Name | Value | Secured |
|---------------|-------|---------|
| `EXCLUDE_SUBSTRINGS` | `ETCIO,ETBRANDEQUITY,ETHR,ETCFO,ETAUTO,ETRETAIL,ETHEALTH,ETTELECOM,ETENERGY,ETREALESTATE,ETIT,ETITSECURITY,ETBFSI,ETGOVERNMENT,ETHOSPITALITY,ETLEGAL,ETTRAVELWORLD,ETINFRA,ETB2B,ETCIOSEA,ETHRSEA,ETHREMEA,ETEduCation,ETEnergyWorldMEA,ETManufacturing,ETPharma,ETGCC,ETEnterpriseAI,ETREALTY,ET ENERGY,ET TRAVEL,ET REALTY` | ❌ |
| `EXCLUDE_PLATFORMS` | `App` | ❌ |

---

## 🔐 Setting Up Service Account JSON

### Step 1: Get Service Account JSON
1. Go to Google Cloud Console
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Create or select your service account
4. Create a new key (JSON format)
5. Download the JSON file

### Step 2: Add to Repository Variables
1. Open the downloaded JSON file
2. Copy the entire content
3. In Bitbucket, create a new variable:
   - **Name**: `GOOGLE_SERVICE_ACCOUNT_JSON`
   - **Value**: Paste the entire JSON content
   - **Secured**: ✅ (Check this box)

---

## 📝 Updated Script Configuration

Now update your script to use environment variables:

```python
# geofetchgsheet.py - Updated Configuration
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleads import ad_manager
from datetime import datetime, timedelta
import pytz
import time
import re
import json

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA')

# GAM setup
GAM_YAMLS = os.getenv('GAM_YAML_FILES', 'googleadsN.yaml,googleads.yaml').split(',')

# Exclusion list for Package Name (case-insensitive)
EXCLUDE_SUBSTRINGS = os.getenv('EXCLUDE_SUBSTRINGS', 'ETCIO,ETBRANDEQUITY,ETHR,ETCFO,ETAUTO,ETRETAIL,ETHEALTH,ETTELECOM,ETENERGY,ETREALESTATE,ETIT,ETITSECURITY,ETBFSI,ETGOVERNMENT,ETHOSPITALITY,ETLEGAL,ETTRAVELWORLD,ETINFRA,ETB2B,ETCIOSEA,ETHRSEA,ETHREMEA,ETEduCation,ETEnergyWorldMEA,ETManufacturing,ETPharma,ETGCC,ETEnterpriseAI,ETREALTY,ET ENERGY,ET TRAVEL,ET REALTY').split(',')

# Exclude platforms
EXCLUDE_PLATFORMS = os.getenv('EXCLUDE_PLATFORMS', 'App').split(',')

def setup_google_sheets():
    """Setup Google Sheets authentication"""
    try:
        # Try to use service account JSON from environment
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            # Parse JSON and create credentials
            service_account_info = json.loads(service_account_json)
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                service_account_info, SCOPES
            )
        else:
            # Fallback to file-based authentication
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                'service-account.json', SCOPES
            )
        
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        print(f"Error setting up Google Sheets: {e}")
        return None

# Update your main function to use the new setup
def main():
    # Setup Google Sheets
    gc = setup_google_sheets()
    if not gc:
        print("Failed to setup Google Sheets authentication")
        return
    
    # Rest of your code...
```

---

## 🔄 Updated Pipeline Configuration

Update your `bitbucket-pipelines.yml` to use the variables:

```yaml
image: python:3.9

definitions:
  steps:
    - step: &setup-environment
        name: Setup Environment
        caches:
          - pip
        script:
          - pip install -r requirements.txt
          - echo "Environment setup complete"

    - step: &run-gam-script
        name: Run GAM Geo Fetch Script
        caches:
          - pip
        script:
          # Create service account JSON file if using environment variable
          - |
            if [ ! -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]; then
              echo "$GOOGLE_SERVICE_ACCOUNT_JSON" > service-account.json
              echo "Service account JSON created from environment variable"
            fi
          - python geofetchgsheet.py
        artifacts:
          - logs/**

pipelines:
  default:
    - step: *setup-environment
    - step: *run-gam-script

  branches:
    main:
      - step: *setup-environment
      - step: *run-gam-script

  pull-requests:
    '**':
      - step: *setup-environment
      - step: *run-gam-script
```

---

## 🧪 Testing Your Variables

### Step 1: Create a Test Pipeline
```yaml
pipelines:
  custom:
    test-variables:
      - step:
          name: Test Repository Variables
          script:
            - echo "Testing repository variables..."
            - echo "GOOGLE_SHEET_ID: $GOOGLE_SHEET_ID"
            - echo "GAM_NETWORK_CODES: $GAM_NETWORK_CODES"
            - echo "EXCLUDE_SUBSTRINGS: $EXCLUDE_SUBSTRINGS"
            - echo "EXCLUDE_PLATFORMS: $EXCLUDE_PLATFORMS"
            - |
              if [ ! -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]; then
                echo "GOOGLE_SERVICE_ACCOUNT_JSON: [SET]"
              else
                echo "GOOGLE_SERVICE_ACCOUNT_JSON: [NOT SET]"
              fi
```

### Step 2: Run the Test
1. Go to **Pipelines** in your repository
2. Click **Run pipeline**
3. Select **Custom** → **test-variables**
4. Click **Run**

---

## 🔒 Security Best Practices

### ✅ Do This
- Mark sensitive variables as **Secured**
- Use service account JSON instead of API keys
- Regularly rotate credentials
- Use workspace-level variables for shared configs

### ❌ Don't Do This
- Commit credentials to your repository
- Use personal access tokens in production
- Share secured variables across public repositories

---

## 🐛 Troubleshooting

### Common Issues

1. **Variable Not Found**
   ```bash
   # Check if variable is set
   echo "Variable value: $VARIABLE_NAME"
   ```

2. **Service Account JSON Issues**
   ```bash
   # Validate JSON format
   echo "$GOOGLE_SERVICE_ACCOUNT_JSON" | jq .
   ```

3. **Permission Errors**
   - Ensure service account has proper permissions
   - Check if Google Sheet is shared with service account email

---

## 📋 Variable Checklist

- [ ] `GOOGLE_SHEET_ID` - Google Sheet ID
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` - Service account credentials (secured)
- [ ] `GAM_NETWORK_CODES` - GAM network codes
- [ ] `GAM_YAML_FILES` - GAM YAML file names
- [ ] `EXCLUDE_SUBSTRINGS` - Package names to exclude
- [ ] `EXCLUDE_PLATFORMS` - Platforms to exclude

---

## 🎯 Quick Setup Commands

### For Local Testing
```bash
# Export variables locally (for testing)
export GOOGLE_SHEET_ID="1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA"
export GAM_NETWORK_CODES="7176,23037861279"
export EXCLUDE_SUBSTRINGS="ETCIO,ETBRANDEQUITY,ETHR,ETCFO,ETAUTO,ETRETAIL,ETHEALTH,ETTELECOM,ETENERGY,ETREALESTATE,ETIT,ETITSECURITY,ETBFSI,ETGOVERNMENT,ETHOSPITALITY,ETLEGAL,ETTRAVELWORLD,ETINFRA,ETB2B,ETCIOSEA,ETHRSEA,ETHREMEA,ETEduCation,ETEnergyWorldMEA,ETManufacturing,ETPharma,ETGCC,ETEnterpriseAI,ETREALTY,ET ENERGY,ET TRAVEL,ET REALTY"
export EXCLUDE_PLATFORMS="App"

# Test your script
python geofetchgsheet.py
```

---

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all variables are set correctly
3. Test with the provided test pipeline
4. Check Bitbucket pipeline logs for detailed error messages 