# GAM Geo Fetch Google Sheets Integration

This project provides a Python script to fetch geo-targeting information from Google Ad Manager (GAM) and update Google Sheets with campaign data including geo targeting, order IDs, trafficker, and creator information.

## 🚀 Features

- **GAM API Integration**: Fetches data from multiple GAM accounts using v202411 API
- **Google Sheets Integration**: Updates Google Sheets with campaign data
- **Smart Caching**: Prevents redundant API calls for better performance
- **Future Date Processing**: Only processes today and future dates for efficiency
- **Multi-Account Support**: Handles multiple GAM network codes
- **Robust Error Handling**: Graceful handling of API errors and edge cases
- **Column Management**: Smart placement of new columns in Google Sheets

## 📋 Prerequisites

- Python 3.7+
- Google Ad Manager API access
- Google Sheets API access
- Valid GAM credentials

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <your-bitbucket-repo-url>
   cd Custom_API_GAM_CPD
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up GAM API credentials**
   
   Create `googleads.yaml` and `googleadsN.yaml` files with your GAM API credentials:
   
   ```yaml
   # googleads.yaml
   network_code: 7176
   application_name: YourAppName
   path_to_private_key_file: path/to/your/private-key.json
   
   # googleadsN.yaml  
   network_code: 23037861279
   application_name: YourAppName
   path_to_private_key_file: path/to/your/private-key.json
   ```

4. **Set up Google Sheets API**
   
   - Enable Google Sheets API in Google Cloud Console
   - Create a service account and download the JSON credentials
   - Share your Google Sheet with the service account email

## 🔧 Configuration

### Environment Variables (Optional)
You can set these environment variables for configuration:

```bash
export GOOGLE_SHEET_ID="your-sheet-id"
export GOOGLE_SHEET_NAME="your-sheet-name"
export GAM_NETWORK_CODES="7176,23037861279"
```

### Script Configuration
Edit the following variables in `geofetchgsheet.py`:

```python
# Google Sheets configuration
SHEET_ID = "1Qx1GhhGUGM_3FWLDM04ygyAezUO2Zf6C4SlhG1h7IQA"
SHEET_NAME = "28 July"

# GAM configuration files
GAM_CONFIG_FILES = ['googleads.yaml', 'googleadsN.yaml']

# Exclusion patterns
EXCLUDE_SUBSTRINGS = ['ETCIO', 'ETBRANDEQUITY']
EXCLUDE_PLATFORMS = ['App']
```

## 📖 Usage

### Basic Usage
```bash
python geofetchgsheet.py
```

### What the script does:
1. **Connects to GAM**: Uses multiple GAM accounts for comprehensive data
2. **Processes Google Sheets**: Identifies sheets that need updating (future dates only)
3. **Fetches Campaign Data**: Searches for campaigns by name and Expresso ID
4. **Extracts Geo Information**: Gets included/excluded geo targeting
5. **Updates Sheets**: Adds geo data, order IDs, trafficker, and creator information

### Output Columns Added:
- `geo included`: Geographic locations included in targeting
- `geo excluded`: Geographic locations excluded from targeting  
- `Order ID`: GAM order identifier
- `Trafficker`: Name of the trafficker
- `Creator`: Name of the creator

## 🔍 Script Features

### Smart Sheet Detection
- Automatically detects date-based sheet names
- Supports various date formats (e.g., "28 July", "July 28", "28/07")
- Only processes today and future dates

### Campaign Search Strategy
1. Search by Campaign Name (partial match)
2. Fallback to Expresso ID search
3. Search in multiple GAM accounts
4. Filter for active SPONSORSHIP line items only

### Performance Optimizations
- **Caching**: Results cached to prevent redundant API calls
- **Batch Updates**: Efficient Google Sheets updates
- **Rate Limiting**: Proper delays to avoid API limits
- **Future Dates Only**: Skips past dates for efficiency

## 🚨 Important Notes

### Security
- **Never commit credentials**: The `.gitignore` excludes `*.yaml` files
- **Use service accounts**: For production, use service account authentication
- **Environment variables**: Store sensitive data in environment variables

### API Limits
- GAM API has rate limits - the script includes delays
- Google Sheets API has quotas - batch updates are used
- Monitor usage in Google Cloud Console

### Data Accuracy
- Script only processes active SPONSORSHIP line items
- Geo data is extracted from line item targeting
- User information is fetched from GAM UserService

## 🐛 Troubleshooting

### Common Issues

1. **API Authentication Errors**
   - Verify your GAM credentials are correct
   - Check that your service account has proper permissions
   - Ensure Google Sheets API is enabled

2. **Sheet Not Found**
   - Verify the SHEET_ID is correct
   - Check that the service account has access to the sheet
   - Ensure the sheet name exists

3. **No Data Found**
   - Check that campaigns exist in GAM
   - Verify the search strings match campaign names
   - Ensure line items are active and of type SPONSORSHIP

4. **Rate Limiting**
   - The script includes delays, but you may need to increase them
   - Monitor API usage in Google Cloud Console

### Debug Mode
The script includes extensive debug logging. Look for `[DEBUG]` messages in the output for troubleshooting.

## 📝 Logging

The script provides detailed logging:
- `[INFO]`: General information about processing
- `[DEBUG]`: Detailed debug information
- `[ERROR]`: Error messages
- `[CACHE]`: Cache hit/miss information
- `[SKIP]`: Skipped rows information

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the debug logs
3. Create an issue in the repository
4. Contact the development team

## 🔄 Version History

- **v1.0.0**: Initial release with GAM v202411 API support
- Added multi-account GAM support
- Implemented smart caching
- Added comprehensive error handling
- Future date processing optimization 