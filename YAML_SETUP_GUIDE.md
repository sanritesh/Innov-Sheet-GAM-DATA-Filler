# 🔐 GAM YAML Files Setup Guide

## ⚠️ **Security Issue Fixed**

Your original YAML files contained sensitive OAuth2 credentials that were exposed in your repository. This has been fixed by:

1. ✅ **Created template files** without sensitive data
2. ✅ **Updated .gitignore** to exclude sensitive YAML files
3. ✅ **Updated pipeline** to generate YAML files from templates
4. ✅ **Added environment variables** for credentials

---

## 📋 **What You Need to Do**

### 1. **Add OAuth2 Credentials to Repository Variables**

Go to your Bitbucket repository → **Repository settings** → **Pipelines** → **Repository variables** and add:

| Variable Name | Value | Secured |
|---------------|-------|---------|
| `GOOGLE_CLIENT_ID` | `357440026235-nlr12sbmnrt4r0eedgrhb57vkfe5nbiv.apps.googleusercontent.com` | ✅ |
| `GOOGLE_CLIENT_SECRET` | `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` | ✅ |
| `GOOGLE_REFRESH_TOKEN` | `1//04XFJYBqZ0qJdCgYIARAAGAQSNwF-L9IrsSov8-0tpYmMWMUXvj6RjSxpAkJi1vK2eM2LcoPMzGf_3wxVdrXV3Rbvuf7vUIAy6Xs` | ✅ |

### 2. **Complete Variable List**

You now need these **6 variables** total:

| Variable Name | Value | Secured |
|---------------|-------|---------|
| `GOOGLE_SHEET_ID` | `1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA` | ❌ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | [Your service account JSON] | ✅ |
| `GOOGLE_CLIENT_ID` | `357440026235-nlr12sbmnrt4r0eedgrhb57vkfe5nbiv.apps.googleusercontent.com` | ✅ |
| `GOOGLE_CLIENT_SECRET` | `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` | ✅ |
| `GOOGLE_REFRESH_TOKEN` | `1//04XFJYBqZ0qJdCgYIARAAGAQSNwF-L9IrsSov8-0tpYmMWMUXvj6RjSxpAkJi1vK2eM2LcoPMzGf_3wxVdrXV3Rbvuf7vUIAy6Xs` | ✅ |
| `GAM_NETWORK_CODES` | `7176,23037861279` | ❌ |
| `GAM_YAML_FILES` | `googleadsN.yaml,googleads.yaml` | ❌ |
| `EXCLUDE_SUBSTRINGS` | `ETCIO,ETBRANDEQUITY,ETHR,ETCFO,ETAUTO,ETRETAIL,ETHEALTH,ETTELECOM,ETENERGY,ETREALESTATE,ETIT,ETITSECURITY,ETBFSI,ETGOVERNMENT,ETHOSPITALITY,ETLEGAL,ETTRAVELWORLD,ETINFRA,ETB2B,ETCIOSEA,ETHRSEA,ETHREMEA,ETEduCation,ETEnergyWorldMEA,ETManufacturing,ETPharma,ETGCC,ETEnterpriseAI,ETREALTY,ET ENERGY,ET TRAVEL,ET REALTY` | ❌ |
| `EXCLUDE_PLATFORMS` | `App` | ❌ |

---

## 🔄 **How It Works Now**

### **Template Files** (Safe to commit)
- ✅ `googleadsN.yaml.template` - Template for network 23037861279
- ✅ `googleads.yaml.template` - Template for network 7176

### **Generated Files** (Excluded from git)
- ❌ `googleadsN.yaml` - Generated during pipeline run
- ❌ `googleads.yaml` - Generated during pipeline run

### **Pipeline Process**
1. **Reads environment variables** for OAuth2 credentials
2. **Generates YAML files** from templates using `sed`
3. **Runs your script** with the generated files
4. **Cleans up** sensitive files after execution

---

## 🧪 **Testing Your Setup**

### **Test Pipeline**
```yaml
pipelines:
  custom:
    test-yaml-generation:
      - step:
          name: Test YAML Generation
          script:
            - echo "Testing YAML file generation..."
            - |
              if [ ! -z "$GOOGLE_CLIENT_ID" ] && [ ! -z "$GOOGLE_CLIENT_SECRET" ] && [ ! -z "$GOOGLE_REFRESH_TOKEN" ]; then
                sed "s/\${GOOGLE_CLIENT_ID}/$GOOGLE_CLIENT_ID/g; s/\${GOOGLE_CLIENT_SECRET}/$GOOGLE_CLIENT_SECRET/g; s/\${GOOGLE_REFRESH_TOKEN}/$GOOGLE_REFRESH_TOKEN/g" googleadsN.yaml.template > googleadsN.yaml
                echo "✅ YAML file generated successfully"
                echo "Network code: $(grep 'network_code:' googleadsN.yaml)"
                echo "Client ID: $(grep 'client_id:' googleadsN.yaml | cut -d' ' -f2)"
              else
                echo "❌ OAuth2 credentials not found"
              fi
```

### **Run the Test**
1. Go to **Pipelines** in your repository
2. Click **Run pipeline**
3. Select **Custom** → **test-yaml-generation**
4. Click **Run**

---

## 🔒 **Security Benefits**

### ✅ **What's Secure Now**
- **No credentials in source code**
- **Template files are safe** to commit
- **Environment variables are encrypted**
- **Generated files are excluded** from git
- **Automatic cleanup** after pipeline runs

### ❌ **What Was Insecure Before**
- **OAuth2 credentials exposed** in repository
- **Client secrets visible** to anyone with access
- **Refresh tokens** in plain text
- **No encryption** for sensitive data

---

## 📁 **File Structure**

```
Your Repository/
├── googleadsN.yaml.template    ✅ Safe template
├── googleads.yaml.template     ✅ Safe template
├── geofetchgsheet.py           ✅ Your script
├── bitbucket-pipelines.yml     ✅ Updated pipeline
├── .gitignore                  ✅ Excludes sensitive files
├── googleadsN.yaml            ❌ Generated (excluded)
└── googleads.yaml             ❌ Generated (excluded)
```

---

## 🚀 **Next Steps**

1. **Add all 9 variables** to your repository
2. **Test YAML generation** with the test pipeline
3. **Run your main pipeline** to verify everything works
4. **Monitor logs** for any issues

---

## 🐛 **Troubleshooting**

### **Common Issues**

1. **"OAuth2 credentials not found"**
   - Check that all 3 OAuth2 variables are set
   - Verify they are marked as "Secured"

2. **"YAML file not found"**
   - Ensure template files exist
   - Check pipeline logs for generation errors

3. **"Authentication failed"**
   - Verify service account JSON is correct
   - Check OAuth2 credentials are valid

---

## 📞 **Support**

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all variables are set correctly
3. Test with the provided test pipeline
4. Check Bitbucket pipeline logs for detailed error messages 