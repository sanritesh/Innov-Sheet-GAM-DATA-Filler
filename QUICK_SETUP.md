# 🚀 Quick Repository Variables Setup

## 📋 Required Variables for Your GAM Script

Go to your Bitbucket repository → **Repository settings** → **Pipelines** → **Repository variables** and add these:

### 🔑 Essential Variables

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

## 🔐 Getting Service Account JSON

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Create or select your service account
4. Create a new key (JSON format)
5. Download and copy the entire JSON content
6. Paste it as the value for `GOOGLE_SERVICE_ACCOUNT_JSON` (mark as secured)

## 🧪 Test Your Setup

1. Go to **Pipelines** in your repository
2. Click **Run pipeline**
3. Select **Custom** → **test-variables**
4. Click **Run**

## ✅ What's Been Updated

- ✅ Script now uses environment variables
- ✅ Pipeline configuration updated
- ✅ Test pipeline added
- ✅ Fallback to file-based authentication
- ✅ Comprehensive documentation created

## 📚 Full Documentation

- `REPOSITORY_VARIABLES_SETUP.md` - Complete setup guide
- `VARIABLE_IMPORT_GUIDE.md` - How to import variables from other repos
- `bitbucket-pipelines.yml` - Updated pipeline configuration

## 🎯 Next Steps

1. Add the variables to your repository
2. Test with the test pipeline
3. Run your main pipeline
4. Monitor the logs for any issues 