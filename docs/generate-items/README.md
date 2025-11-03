# Item Generator

Generates shop items from a template JSON with placeholders and quantity specifications.

## Usage

```bash
python generate_items.py template_example.json output.json
```

## Template Format

The template JSON consists of two main parts:

### 1. Template Configuration

```json
{
  "template": {
    "consultation_id_pattern": "CONSULTING-{{YEAR}}-{{RANDOM_4}}-INVOICE-{{INDEX:06d}}",
    "admin_telegram_username": "YOUR_ADMIN_USERNAME"
  }
}
```

This defines global settings that can be reused in items.

### 2. Item Templates

```json
{
  "items": [
    {
      "quantity": 50,
      "category_id": 1,
      "subcategory_id": 2,
      "private_data": "Text with {{PLACEHOLDER}}",
      "price": 29.99,
      "description": "USB 3.0 Flash Drive - 64GB",
      "is_physical": true,
      "shipping_cost": 5.55,
      "allows_packstation": false
    }
  ]
}
```

**Important:** The `quantity` field determines how many items will be generated from this template.

## Available Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{{INDEX}}` | Sequential number | 1, 2, 3, ... |
| `{{INDEX:06d}}` | Sequential number with padding | 000001, 000002, ... |
| `{{YEAR}}` | Current year | 2025 |
| `{{RANDOM_4}}` | 4 random uppercase letters | ABCD, XYZW, ... |
| `{{RANDOM_DIGITS_6}}` | 6 random digits | 123456, 987654, ... |
| `{{UUID}}` | UUID4 | 550e8400-e29b-41d4-a716-446655440000 |
| `{{LICENSE_KEY}}` | Uses pattern from template | LICENSE-2025-ABCDEFGH |
| `{{ADMIN_TELEGRAM}}` | Admin username from template | YOUR_ADMIN_USERNAME |

## Examples

### Example 1: Simple Duplication

```json
{
  "items": [
    {
      "quantity": 50,
      "category_id": 1,
      "subcategory_id": 2,
      "private_data": null,
      "price": 29.99,
      "description": "USB 3.0 Flash Drive - 64GB",
      "is_physical": true,
      "shipping_cost": 5.0,
      "allows_packstation": true
    }
  ]
}
```

Creates 50 identical USB drive items with IDs 1-50.

### Example 2: Items with Individual IDs

```json
{
  "template": {
    "license_key_pattern": "LICENSE-{{YEAR}}-{{RANDOM_8}}"
  },
  "items": [
    {
      "quantity": 100,
      "category_id": 4,
      "subcategory_id": 7,
      "private_data": "License Key: {{LICENSE_KEY}}",
      "price": 49.99,
      "description": "Software License #{{INDEX}} (Key: {{LICENSE_KEY}})",
      "is_physical": false,
      "shipping_cost": 0.0,
      "allows_packstation": false
    }
  ]
}
```

Creates 100 software license items, each with a unique key like:
- `LICENSE-2025-ABCDEFGH`
- `LICENSE-2025-XYZWQRST`
- etc.

## Output

The script generates a JSON with all items:

```json
{
  "items": [
    {
      "id": 1,
      "category_id": 1,
      "subcategory_id": 2,
      "private_data": null,
      "price": 29.99,
      "description": "USB 3.0 Flash Drive - 64GB",
      "is_physical": true,
      "shipping_cost": 5.0,
      "allows_packstation": true,
      "is_sold": false,
      "is_new": true
    },
    ...
  ]
}
```

The `id` is automatically assigned sequentially, starting from 1.

## HTML Formatting in private_data

Telegram supports HTML formatting in messages. You can use the following tags directly in `private_data`:

### Supported HTML Tags

| Tag | Purpose | Example |
|-----|---------|---------|
| `<b>text</b>` | Bold text | `<b>Important!</b>` |
| `<i>text</i>` | Italic text | `<i>Note</i>` |
| `<code>text</code>` | Monospace code | `<code>KEY-123-ABC</code>` |
| `<a href="url">text</a>` | Clickable link | `<a href="https://t.me/username">  Chat</a>` |
| `\n` | Line break | Use `\n` for new lines |

### Example: Clickable Telegram Contact Button

**Template:**
```json
{
  "private_data": "License Key: <code>{{LICENSE_KEY}}</code>\n\n<a href=\"https://t.me/username?text=License%20%23{{LICENSE_KEY}}\">  Contact Support</a>\n\n<b>Important Notes:</b>\n• Valid for 1 year\n• Free updates included"
}
```

**Rendered in Telegram:**
```
License Key: LICENSE-2025-ABCDEFGH

  Contact Support  [clickable button]

Important Notes:
• Valid for 1 year
• Free updates included
```

### Telegram Deep Links with Pre-filled Messages

To open a chat with a pre-filled message, use:

```
https://t.me/USERNAME?text=YOUR_MESSAGE
```

**URL Encoding:** Spaces become `%20`, `#` becomes `%23`

**Examples:**

| Link | Opens Chat With |
|------|----------------|
| `https://t.me/username` | Empty message |
| `https://t.me/username?text=Hello` | "Hello" pre-filled |
| `https://t.me/username?text=Order%20%23123` | "Order #123" pre-filled |
| `https://t.me/username?text=License%20%23{{LICENSE_KEY}}` | "License #LICENSE-2025-ABCDEFGH" |

### Complete Example

```json
{
  "template": {
    "license_key_pattern": "LICENSE-{{YEAR}}-{{RANDOM_8}}",
    "telegram_username": "yourshopbot"
  },
  "items": [
    {
      "quantity": 50,
      "category_id": 4,
      "subcategory_id": 7,
      "private_data": "  <b>License Key:</b> <code>{{LICENSE_KEY}}</code>\n\n<a href=\"https://t.me/{{TELEGRAM_USERNAME}}?text=License%20%23{{LICENSE_KEY}}\">  Contact Support</a>\n\n<b>Features:</b>\n• Valid for 1 year\n• Free updates\n• Email support\n\n<i>Please provide your key when contacting support.</i>",
      "price": 49.99,
      "description": "Premium Software License - Key: {{LICENSE_KEY}}",
      "is_physical": false,
      "shipping_cost": 0.0,
      "allows_packstation": false
    }
  ]
}
```

This will show the user a clickable button that:
1. Opens Telegram
2. Starts a chat with `@yourshopbot`
3. Pre-fills the message: "License #LICENSE-2025-ABCDEFGH"
4. User clicks "Send" to contact support

### Important Notes

- **Test your HTML:** Always test the rendered output in Telegram before mass-generating items
- **Escape quotes:** Use `\"` inside JSON strings for quotes in HTML
- **No `+` in usernames:** Use `@username` format, not phone numbers with `+`
- **URL encoding:** Pre-fill text must be URL-encoded (spaces = `%20`, `#` = `%23`)

## Workflow

1. Create a template JSON (see `template_example.json`)
2. Define a template for each item type with `quantity`
3. Use placeholders for individual values
4. **Format private_data with HTML for clickable links**
5. Run the script
6. **Test one item in Telegram before importing all**
7. Import the generated JSON into the database