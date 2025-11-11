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
{{ADMIN_TELEGRAM}}  - Admin username/ID from template.admin_telegram_username
                      (or template.admin_telegram_id as fallback)
{{UUID}}            - Generates a UUID4

Tiered Pricing Support:
-----------------------
Items can use legacy flat pricing OR tiered bulk pricing:

**Legacy pricing (flat rate):**
  "price": 49.99

**Tiered pricing (bulk discounts):**
  "price_tiers": [
    {"min_quantity": 1, "unit_price": 11.00},
    {"min_quantity": 5, "unit_price": 10.00},
    {"min_quantity": 10, "unit_price": 9.00}
  ]

Shipping Tiers Support:
-----------------------
Subcategories can define quantity-based shipping type selection:

**Legacy shipping (flat rate per item):**
  "shipping_cost": 5.00

**Dynamic shipping tiers (quantity-based):**
  "shipping_tiers": [
    {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
    {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
    {"min_quantity": 11, "max_quantity": null, "shipping_type": "paket_2kg"}
  ]

How Shipping Tiers Work:
- Defined at subcategory level (all items in subcategory share same logic)
- Automatically selects shipping type based on cart quantity
- References shipping types from shipping_types/{country}.json
- Example: 1-5 items → Maxibrief, 6-10 → Päckchen, 11+ → Paket 2kg
- Only for physical items (is_physical: true)

Best Practices:
- First tier should start with min_quantity: 1
- Last tier should have max_quantity: null (unlimited)
- No gaps or overlaps in quantity ranges
- shipping_type must exist in shipping_types/de.json
- Use EITHER shipping_cost OR shipping_tiers, not both

How Tiered Pricing Works:
- Each tier defines a minimum quantity and unit price
- When customers buy multiple items, the bot applies the best discount
- Uses greedy algorithm: applies largest qualifying tier first
- Example: Buying 12 items with tiers above:
  * 10 items @ €9.00 = €90.00
  * 2 items @ €11.00 = €22.00
  * Total: €112.00 (instead of €132.00 at flat rate)

Best Practices:
- First tier should always have min_quantity: 1 (base price)
- Tiers must be sorted by min_quantity (ascending)
- Unit prices should decrease as quantity increases
- Use EITHER price OR price_tiers, not both
- If price_tiers is present, base price is derived from min_quantity=1

Generated Output:
- Items with price_tiers will include the full tier array in output
- The bot's parser automatically creates PriceTier database entries
- Cart system calculates optimal tier breakdown at checkout

Telegram Deep Links in private_data:
-------------------------------------
You can create clickable links to contact support with pre-filled messages:

**Supported Protocols:**
- https://t.me/USERNAME?text=MESSAGE (works in browser and app)
- t.me/USERNAME?text=MESSAGE (auto-converted to https://)
- tg://resolve?domain=USERNAME&text=MESSAGE (opens directly in app)

**URL Parameters:**
- text=MESSAGE - Pre-filled message text (URL-encoded: space=%20, #=%23)
- start=PAYLOAD - Bot start parameter
- Combine: ?start=PAYLOAD&text=MESSAGE

**Example:**
  "<a href=\"https://t.me/{{ADMIN_TELEGRAM}}?text=License%20%23{{LICENSE_KEY}}\">📱 Contact Support</a>"

**Important:** Link parameters are NOT visible to user, only clickable text is shown.

Example Template JSON:
----------------------
{
  "template": {
    "license_key_pattern": "LICENSE-{{YEAR}}-{{RANDOM_8}}",
    "admin_telegram_username": "YOUR_ADMIN_USERNAME",
    "consultation_id_pattern": "CONSULT-{{YEAR}}-{{INDEX:06d}}"
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
      "private_data": "<b>License Key:</b> <code>{{LICENSE_KEY}}</code>\\n\\n<a href=\\\"https://t.me/{{ADMIN_TELEGRAM}}?text=License%20%23{{LICENSE_KEY}}\\\">📱 Contact Support</a>",
      "description": "Premium Software License - Key: {{LICENSE_KEY}}",
      "is_physical": false,
      "shipping_cost": 0.0,
      "allows_packstation": false,
      "price_tiers": [
        {"min_quantity": 1, "unit_price": 49.99},
        {"min_quantity": 10, "unit_price": 44.99},
        {"min_quantity": 25, "unit_price": 39.99}
      ]
    }
  ]
}

Output:
-------
Generates a structured JSON with items and subcategories:

{
  "items": [
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
      "allows_packstation": false,
      "price_tiers": [
        {"min_quantity": 1, "unit_price": 49.99},
        {"min_quantity": 10, "unit_price": 44.99},
        {"min_quantity": 25, "unit_price": 39.99}
      ]
    }
  ],
  "subcategories": [
    {
      "name": "USB Storage Devices",
      "category": "Hardware Products",
      "shipping_tiers": [
        {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
        {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
        {"min_quantity": 11, "max_quantity": null, "shipping_type": "paket_2kg"}
      ]
    }
  ]
}

Notes:
- Items with price_tiers include both "price" (base) and "price_tiers" array
- Subcategories with shipping_tiers are output separately (subcategory-level)
- The bot's parser handles both structures automatically
- shipping_tiers are only included if defined in the template
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

        # {{ADMIN_TELEGRAM}} - From template (supports both username and ID)
        if "{{ADMIN_TELEGRAM}}" in result:
            # Try admin_telegram_username first, fallback to admin_telegram_id
            admin_value = self.template_settings.get("admin_telegram_username",
                          self.template_settings.get("admin_telegram_id", ""))
            result = result.replace("{{ADMIN_TELEGRAM}}", admin_value)

        # {{LICENSE_KEY}} - Generated from pattern
        if "{{LICENSE_KEY}}" in result:
            pattern = self.template_settings.get("license_key_pattern", "LICENSE-{{YEAR}}-{{RANDOM_8}}")
            license_key = self.replace_placeholders(pattern, index, item_context)
            result = result.replace("{{LICENSE_KEY}}", license_key)

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

        # Extract price_tiers if present (needs deep copy for each item)
        has_price_tiers = "price_tiers" in template
        price_tiers = template.get("price_tiers")

        for i in range(1, quantity + 1):
            item = template.copy()
            # Keep category and subcategory as names, not IDs
            item["category"] = category_name
            item["subcategory"] = subcategory_name

            # Deep copy price_tiers for each item (avoid reference sharing)
            if has_price_tiers:
                import copy
                item["price_tiers"] = copy.deepcopy(price_tiers)

            # Replace placeholders in all string fields
            for key, value in item.items():
                if isinstance(value, str):
                    item[key] = self.replace_placeholders(value, i)

            items.append(item)

        return items

    def generate_all(self) -> dict:
        """
        Generate all items and subcategories from templates.

        Returns:
            Dict with 'items' (list) and 'subcategories' (list with shipping_tiers)
        """
        # Generate flat items array with category/subcategory names
        all_items = []

        # Track subcategories with their shipping_tiers
        subcategories_with_tiers = {}

        for template in self.template_items:
            # Extract shipping_tiers if present (subcategory-level)
            shipping_tiers = template.get("shipping_tiers")
            subcategory_name = template.get("subcategory")

            # Store shipping_tiers for this subcategory
            if shipping_tiers and subcategory_name:
                if subcategory_name not in subcategories_with_tiers:
                    subcategories_with_tiers[subcategory_name] = {
                        "name": subcategory_name,
                        "category": template.get("category"),
                        "shipping_tiers": shipping_tiers
                    }

            # Remove shipping_tiers before generating items (item-level doesn't have this)
            template_copy = template.copy()
            if "shipping_tiers" in template_copy:
                del template_copy["shipping_tiers"]

            items = self.generate_items_from_template(template_copy)
            all_items.extend(items)

        # Build output structure
        output = {
            "items": all_items
        }

        # Add subcategories with shipping_tiers if any exist
        if subcategories_with_tiers:
            output["subcategories"] = list(subcategories_with_tiers.values())

        return output


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
    items = output_data.get("items", [])
    subcategories = output_data.get("subcategories", [])

    total_items = len(items)
    total_subcategories_with_tiers = len(subcategories)

    print(f"✓ Successfully generated {total_items} items")
    if total_subcategories_with_tiers > 0:
        print(f"✓ Generated {total_subcategories_with_tiers} subcategories with shipping tiers")
    print(f"✓ Output written to: {output_file}")

    # Breakdown by category
    category_counts = {}
    for item in items:
        cat_name = item.get("category")
        category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

    print("\nBreakdown by category:")
    for cat_name, count in sorted(category_counts.items()):
        print(f"  {cat_name}: {count} items")

    # Show shipping tier subcategories
    if subcategories:
        print("\nSubcategories with shipping tiers:")
        for subcat in subcategories:
            tier_count = len(subcat.get("shipping_tiers", []))
            print(f"  {subcat['name']}: {tier_count} tiers")


if __name__ == "__main__":
    main()