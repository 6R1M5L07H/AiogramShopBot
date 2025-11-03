#!/usr/bin/env python3
"""
Item Generator Script
=====================

This script generates shop items from a template JSON with placeholders.

Usage:
------
    python generate_items.py input_template.json output_items.json

How it works:
-------------
1. Reads a template JSON with item templates
2. Each template has a 'quantity' field (number of items to generate)
3. Placeholders in private_data and description are replaced
4. Generates final items with unique IDs

Available Placeholders:
-----------------------
{{INDEX}}           - Sequential number (1, 2, 3, ...)
{{INDEX:06d}}       - Sequential number with padding (000001, 000002, ...)
{{YEAR}}            - Current year (2025)
{{RANDOM_N}}        - N random uppercase letters (e.g. {{RANDOM_4}} → ABCD)
{{RANDOM_DIGITS_N}} - N random digits (e.g. {{RANDOM_DIGITS_6}} → 123456)
{{LICENSE_KEY}}     - Uses pattern from template.license_key_pattern
{{ADMIN_TELEGRAM}}  - Admin username from template.admin_telegram_username
{{UUID}}            - Generates a UUID4

Example Template JSON:
----------------------
{
  "template": {
    "license_key_pattern": "LICENSE-{{YEAR}}-{{RANDOM_8}}",
    "admin_telegram_username": "YOUR_ADMIN_USERNAME"
  },
  "categories": [
    {"name": "Digital Products"},
    {"name": "Hardware Products"}
  ],
  "subcategories": [
    {"name": "Software Licenses", "category": "Digital Products"},
    {"name": "USB Storage Devices", "category": "Hardware Products"}
  ],
  "items": [
    {
      "quantity": 50,
      "category": "Hardware Products",
      "subcategory": "USB Storage Devices",
      "private_data": null,
      "price": 29.99,
      "description": "USB 3.0 Flash Drive - 64GB",
      "is_physical": true,
      "shipping_cost": 5.00,
      "allows_packstation": true
    },
    {
      "quantity": 100,
      "category": "Digital Products",
      "subcategory": "Software Licenses",
      "private_data": "License Key: {{LICENSE_KEY}}\\n\\nContact: https://t.me/{{ADMIN_TELEGRAM}}",
      "price": 49.99,
      "description": "Premium Software License - Key: {{LICENSE_KEY}}",
      "is_physical": false,
      "shipping_cost": 0.0,
      "allows_packstation": false
    }
  ]
}

Output:
-------
Generates a flat JSON array compatible with the bot's parser:
[
  {
    "category": "Hardware Products",
    "subcategory": "USB Storage Devices",
    "private_data": "",
    "price": 29.99,
    "description": "USB 3.0 Flash Drive - 64GB",
    "is_physical": true,
    "shipping_cost": 5.00,
    "allows_packstation": true
  },
  {
    "category": "Digital Products",
    "subcategory": "Software Licenses",
    "private_data": "License Key: LICENSE-2025-ABCD1234",
    "price": 49.99,
    "description": "Premium Software License",
    "is_physical": false,
    "shipping_cost": 0.0,
    "allows_packstation": false
  }
]
"""

import json
import random
import re
import string
import sys
import uuid
from datetime import datetime
from pathlib import Path


class ItemGenerator:
    """Generator for shop items from templates with placeholders"""

    def __init__(self, template_config: dict):
        """
        Initialize the generator with template configuration.

        Args:
            template_config: Dict with 'template', 'categories', 'subcategories', and 'items' keys
        """
        self.template_settings = template_config.get("template", {})
        self.categories = template_config.get("categories", [])
        self.subcategories = template_config.get("subcategories", [])
        self.template_items = template_config.get("items", [])
        self.global_item_id = 1

        # Build name-to-ID mappings
        self.category_name_to_id = {}
        self.subcategory_name_to_id = {}

    def replace_placeholders(self, text: str, index: int, item_context: dict = None) -> str:
        """
        Replace placeholders in a text string.

        Args:
            text: String with placeholders
            index: Current iteration (1-based)
            item_context: Additional context for special placeholders

        Returns:
            String with replaced placeholders
        """
        if text is None:
            return None

        item_context = item_context or {}
        result = text

        # {{YEAR}} - Current year
        result = result.replace("{{YEAR}}", str(datetime.now().year))

        # {{INDEX}} or {{INDEX:FORMAT}} - Sequential number
        index_pattern = r'\{\{INDEX(?::([^}]+))?\}\}'
        for match in re.finditer(index_pattern, result):
            format_spec = match.group(1)
            if format_spec:
                formatted_index = format(index, format_spec)
            else:
                formatted_index = str(index)
            result = result.replace(match.group(0), formatted_index)

        # {{RANDOM_N}} - N random uppercase letters
        random_pattern = r'\{\{RANDOM_(\d+)\}\}'
        for match in re.finditer(random_pattern, result):
            length = int(match.group(1))
            random_string = ''.join(random.choices(string.ascii_uppercase, k=length))
            result = result.replace(match.group(0), random_string)

        # {{RANDOM_DIGITS_N}} - N random digits
        digits_pattern = r'\{\{RANDOM_DIGITS_(\d+)\}\}'
        for match in re.finditer(digits_pattern, result):
            length = int(match.group(1))
            random_digits = ''.join(random.choices(string.digits, k=length))
            result = result.replace(match.group(0), random_digits)

        # {{UUID}} - UUID4
        result = result.replace("{{UUID}}", str(uuid.uuid4()))

        # {{ADMIN_TELEGRAM}} - From template
        if "{{ADMIN_TELEGRAM}}" in result:
            admin_id = self.template_settings.get("admin_telegram_id", "")
            result = result.replace("{{ADMIN_TELEGRAM}}", admin_id)

        # {{CONSULTATION_ID}} - Generated from pattern
        if "{{CONSULTATION_ID}}" in result:
            pattern = self.template_settings.get("consultation_id_pattern", "CONSULT-{{INDEX:06d}}")
            consultation_id = self.replace_placeholders(pattern, index, item_context)
            result = result.replace("{{CONSULTATION_ID}}", consultation_id)

        return result

    def generate_items_from_template(self, template: dict) -> list[dict]:
        """
        Generate items from a template.

        Args:
            template: Template item with 'quantity' field

        Returns:
            List of generated items
        """
        quantity = template.pop("quantity", 1)
        items = []

        # Keep category and subcategory as string names (for parser compatibility)
        category_name = template.get("category")
        subcategory_name = template.get("subcategory")

        for i in range(1, quantity + 1):
            item = template.copy()
            # Keep category and subcategory as names, not IDs
            item["category"] = category_name
            item["subcategory"] = subcategory_name

            # Replace placeholders in all string fields
            for key, value in item.items():
                if isinstance(value, str):
                    item[key] = self.replace_placeholders(value, i)

            items.append(item)

        return items

    def generate_all(self) -> list[dict]:
        """
        Generate all items from all templates.

        Returns:
            Flat list of items (parser-compatible format)
        """
        # Generate flat items array with category/subcategory names
        all_items = []
        for template in self.template_items:
            items = self.generate_items_from_template(template.copy())
            all_items.extend(items)

        return all_items


def main():
    """Main function - CLI entry point"""

    if len(sys.argv) != 3:
        print("Usage: python generate_items.py <input_template.json> <output_items.json>")
        print("\nExample:")
        print("  python generate_items.py template.json output.json")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    # Load template JSON
    if not input_file.exists():
        print(f"Error: Input file '{input_file}' does not exist")
        sys.exit(1)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            template_config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}")
        sys.exit(1)

    # Generate items
    generator = ItemGenerator(template_config)
    output_data = generator.generate_all()

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print statistics
    total_items = len(output_data)

    print(f"✓ Successfully generated {total_items} items")
    print(f"✓ Output written to: {output_file}")

    # Breakdown by category
    category_counts = {}
    for item in output_data:
        cat_name = item.get("category")
        category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

    print("\nBreakdown by category:")
    for cat_name, count in sorted(category_counts.items()):
        print(f"  {cat_name}: {count} items")


if __name__ == "__main__":
    main()