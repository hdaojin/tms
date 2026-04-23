#!/usr/bin/env python
"""Convert YAML fixtures to JSON format"""
import yaml
import json
from pathlib import Path
from datetime import datetime

def convert_fixture(yaml_file, json_file, add_timestamps=True):
    """Convert a YAML fixture file to JSON and add timestamps if missing"""
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Add created_at and updated_at timestamps if missing
    if add_timestamps:
        now = datetime.now().isoformat()
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'fields' in item:
                    if 'created_at' not in item['fields']:
                        item['fields']['created_at'] = now
                    if 'updated_at' not in item['fields']:
                        item['fields']['updated_at'] = now
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Converted {yaml_file} → {json_file}")

if __name__ == '__main__':
    fixtures_dir = Path('behaviors/fixtures')
    
    # Convert categories.yaml
    convert_fixture(
        fixtures_dir / 'categories.yaml',
        fixtures_dir / 'categories.json',
        add_timestamps=True
    )
    
    # Convert items.yaml
    convert_fixture(
        fixtures_dir / 'items.yaml',
        fixtures_dir / 'items.json',
        add_timestamps=True
    )
    
    print("\nAll fixtures converted successfully!")
