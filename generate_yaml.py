#!/usr/bin/env python3
"""
Script to generate GAM YAML files from templates using environment variables.
This is safer than using sed/awk for complex credential substitution.
"""

import os
import sys

def generate_yaml_from_template(template_file, output_file):
    """Generate YAML file from template by replacing environment variable placeholders."""
    try:
        # Read template file
        with open(template_file, 'r') as f:
            content = f.read()
        
        # Get environment variables
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')
        
        # Replace placeholders
        content = content.replace('${GOOGLE_CLIENT_ID}', client_id or '')
        content = content.replace('${GOOGLE_CLIENT_SECRET}', client_secret or '')
        content = content.replace('${GOOGLE_REFRESH_TOKEN}', refresh_token or '')
        
        # Write output file
        with open(output_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Generated {output_file} from {template_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating {output_file}: {e}")
        return False

def main():
    """Main function to generate both YAML files."""
    print("🔧 Generating GAM YAML files from templates...")
    
    # Check if required environment variables are set
    required_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("   Using existing YAML files if available")
        return
    
    # Generate YAML file for network 23037861279
    success = True
    success &= generate_yaml_from_template('googleadsN.yaml.template', 'googleadsN.yaml')
    
    if success:
        print("✅ All YAML files generated successfully!")
    else:
        print("❌ Some YAML files failed to generate")
        sys.exit(1)

if __name__ == "__main__":
    main() 