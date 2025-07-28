# 🔄 Repository Variable Import Guide

This guide explains different methods to import repository variables from other repositories in Bitbucket.

## 📋 Methods Overview

### 1. **Bitbucket API Method** (Recommended)
Use the Bitbucket REST API to fetch variables from another repository.

### 2. **Shared Configuration Repository**
Store common variables in a dedicated configuration repository.

### 3. **Environment File Method**
Use shared environment files across repositories.

### 4. **Pipeline Variables**
Reference variables from other pipelines.

---

## 🚀 Method 1: Bitbucket API

### Step 1: Create Access Token
1. Go to Bitbucket Settings → App passwords
2. Create a new app password with repository read permissions
3. Save the token securely

### Step 2: Add to Your Pipeline
```yaml
# bitbucket-pipelines.yml
pipelines:
  custom:
    import-variables:
      - step:
          name: Import Variables from Other Repo
          script:
            # Install jq for JSON parsing
            - apt-get update && apt-get install -y jq
            
            # Fetch variables from another repository
            - |
              curl -X GET \
                -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
                "https://api.bitbucket.org/2.0/repositories/your-org/other-repo/pipelines_config/variables/" \
                | jq -r '.values[] | "export " + .key + "=" + .value' > imported_vars.sh
            
            # Source the variables
            - source imported_vars.sh
            
            # Use the imported variables
            - echo "Using imported variable: $IMPORTED_VAR"
```

### Step 3: Set Up Repository Variables
In your current repository, add:
- `BITBUCKET_ACCESS_TOKEN`: Your app password token

---

## 📁 Method 2: Shared Configuration Repository

### Step 1: Create Config Repository
Create a repository (e.g., `shared-config`) with common variables:

```json
// shared-config.json
{
  "GAM_NETWORK_CODES": "7176,23037861279",
  "GOOGLE_SHEET_ID": "1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA",
  "EXCLUDE_SUBSTRINGS": "ETCIO,ETBRANDEQUITY",
  "EXCLUDE_PLATFORMS": "App"
}
```

### Step 2: Fetch in Pipeline
```yaml
pipelines:
  custom:
    import-config:
      - step:
          name: Import Shared Configuration
          script:
            # Fetch shared configuration
            - |
              curl -X GET \
                -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
                "https://api.bitbucket.org/2.0/repositories/your-org/shared-config/src/main/shared-config.json" \
                -o shared-config.json
            
            # Parse and export variables
            - |
              export GAM_NETWORK_CODES=$(jq -r '.GAM_NETWORK_CODES' shared-config.json)
              export GOOGLE_SHEET_ID=$(jq -r '.GOOGLE_SHEET_ID' shared-config.json)
              export EXCLUDE_SUBSTRINGS=$(jq -r '.EXCLUDE_SUBSTRINGS' shared-config.json)
              export EXCLUDE_PLATFORMS=$(jq -r '.EXCLUDE_PLATFORMS' shared-config.json)
```

---

## 🔧 Method 3: Environment File Method

### Step 1: Create Shared Environment File
In a shared repository, create `shared.env`:

```bash
# shared.env
GAM_NETWORK_CODES=7176,23037861279
GOOGLE_SHEET_ID=1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA
EXCLUDE_SUBSTRINGS=ETCIO,ETBRANDEQUITY
EXCLUDE_PLATFORMS=App
```

### Step 2: Import in Pipeline
```yaml
pipelines:
  custom:
    import-env:
      - step:
          name: Import Environment Variables
          script:
            # Fetch shared environment file
            - |
              curl -X GET \
                -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
                "https://api.bitbucket.org/2.0/repositories/your-org/shared-config/src/main/shared.env" \
                -o shared.env
            
            # Source the environment file
            - source shared.env
```

---

## 🔗 Method 4: Pipeline Variables Reference

### Step 1: Set Up Workspace Variables
In Bitbucket Workspace Settings → Pipelines → Repository variables:
- Add variables that reference other repositories

### Step 2: Use in Pipeline
```yaml
pipelines:
  default:
    - step:
        name: Use Workspace Variables
        script:
          - echo "Using workspace variable: $WORKSPACE_VAR"
          - echo "Using imported variable: $IMPORTED_VAR"
```

---

## 🛠️ Implementation Examples

### Example 1: GAM Configuration Import
```yaml
pipelines:
  custom:
    import-gam-config:
      - step:
          name: Import GAM Configuration
          script:
            # Fetch GAM configuration from shared repo
            - |
              curl -X GET \
                -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
                "https://api.bitbucket.org/2.0/repositories/times_internet/gam-config/src/main/config.json" \
                -o gam-config.json
            
            # Export GAM variables
            - |
              export GAM_NETWORK_CODE_1=$(jq -r '.network_code_1' gam-config.json)
              export GAM_NETWORK_CODE_2=$(jq -r '.network_code_2' gam-config.json)
              export GAM_API_VERSION=$(jq -r '.api_version' gam-config.json)
            
            # Run GAM script with imported config
            - python geofetchgsheet.py
```

### Example 2: Google Sheets Configuration
```yaml
pipelines:
  custom:
    import-sheets-config:
      - step:
          name: Import Google Sheets Config
          script:
            # Fetch sheets configuration
            - |
              curl -X GET \
                -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
                "https://api.bitbucket.org/2.0/repositories/times_internet/sheets-config/src/main/sheets-config.json" \
                -o sheets-config.json
            
            # Export sheet variables
            - |
              export SHEET_ID=$(jq -r '.sheet_id' sheets-config.json)
              export SHEET_NAME=$(jq -r '.sheet_name' sheets-config.json)
              export SERVICE_ACCOUNT_EMAIL=$(jq -r '.service_account_email' sheets-config.json)
```

---

## 🔒 Security Considerations

### ✅ Best Practices
- Use app passwords with minimal required permissions
- Store sensitive data in encrypted repository variables
- Use workspace-level variables for shared configurations
- Regularly rotate access tokens

### ❌ Avoid
- Hardcoding credentials in configuration files
- Using personal access tokens in production
- Sharing sensitive variables across public repositories

---

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   # Check token permissions
   curl -X GET \
     -H "Authorization: Bearer $BITBUCKET_ACCESS_TOKEN" \
     "https://api.bitbucket.org/2.0/user"
   ```

2. **Repository Access**
   - Ensure the app password has repository read access
   - Verify the repository path is correct
   - Check if the repository is private and accessible

3. **Variable Parsing**
   ```bash
   # Debug JSON parsing
   jq '.' shared-config.json
   ```

---

## 📚 Additional Resources

- [Bitbucket REST API Documentation](https://developer.atlassian.com/cloud/bitbucket/rest/)
- [Bitbucket Pipelines Variables](https://support.atlassian.com/bitbucket-cloud/docs/variables-in-pipelines/)
- [App Passwords vs API Tokens](https://support.atlassian.com/bitbucket-cloud/docs/api-tokens/)

---

## 🎯 Quick Start

1. **Choose a method** based on your needs
2. **Set up access tokens** with appropriate permissions
3. **Create shared configuration** if using methods 2-3
4. **Add pipeline configuration** to your repository
5. **Test the import** with a custom pipeline
6. **Deploy to production** when ready 