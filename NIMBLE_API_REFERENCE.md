# Nimble CRM API -- Complete Endpoint Reference

## Overview

**Base URL (API Key auth):** `https://app.nimble.com/api/v1/`
**Base URL (OAuth):** `https://api.nimble.com/api/v1/`

**Authentication:** Bearer token in `Authorization` header.
```
Authorization: Bearer <API_KEY_OR_OAUTH_TOKEN>
```

**Content-Type:** `application/json` for all POST/PUT requests.

**API Version:** 1.3.0 (per readthedocs)

**API Scopes:** `basic` (User & Company Info), `contacts`, `deals`
  - Can be sent as `basic,contacts,deals` or `basic+contacts+deals`

**Sources:** Compiled from nimble.readthedocs.io, support.nimble.com, nimble.com blog, Pipedream components, node-nimble-api, NimbleApi Ruby gem, Endgrate articles, Make.com integration docs, Celigo docs.

---

## 1. USER / ACCOUNT

### 1.1 Get Current User Info
```
GET /api/v1/myself
```
**Parameters:** None
**Response:** Current user object with user info, company details.

---

## 2. CONTACTS -- Basic CRUD

### 2.1 List Contacts
```
GET /api/v1/contacts
```
**Query Parameters:**

| Parameter     | Default   | Description |
|---------------|-----------|-------------|
| `fields`      | all       | Comma-separated list of field names to return |
| `tags`        | 1         | Include tags in results (1=yes, 0=no) |
| `per_page`    | 30        | Items per page |
| `page`        | 1         | Page number (starts at 1) |
| `sort`        | none      | Sort field and order (asc/desc); max 100 contacts when sorting |
| `record_type` | `all`     | `person`, `company`, or `all` |
| `keyword`     | empty     | Simple search on indexed fields |
| `query`       | empty     | Advanced search JSON (incompatible with `record_type` and `keyword`) |

**Response:**
```json
{
  "meta": {
    "page": 1,
    "pages": 1,
    "per_page": 30,
    "total": 2
  },
  "resources": [ /* array of contact objects */ ]
}
```

### 2.2 List Contact IDs Only
```
GET /api/v1/contacts/ids
```
Same parameters as 2.1. Returns only contact identifiers instead of full objects.

### 2.3 Search Contacts (Advanced)
```
GET /api/v1/contacts
```
Uses the `query` parameter with URL-encoded JSON.

**Query structure:**
```json
{"and": [
  {"first name": {"is": "Jack"}},
  {"last name": {"is": "Daniels"}}
]}
```
**Operators:** `is`, `is_not`, `contains`, `does_not_contain`, `is_empty`, `is_not_empty`, `range` (for dates)
**Joins:** `and`, `or`
**Max occurrences:** 11 per request

### 2.4 Get Contact(s) by ID
```
GET /api/v1/contact/<contact_id>
```
**Query Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fields`  | all     | Comma-separated field names |
| `tags`    | 1       | Include tags |

Multiple IDs can be comma-separated: `GET /api/v1/contact/<id1>,<id2>`

**Response:** Single contact object (or array if multiple IDs).

### 2.5 Create Contact
```
POST /api/v1/contact
```
**Request Body:**
```json
{
  "record_type": "person",
  "fields": {
    "first name": [{"value": "Jack", "modifier": ""}],
    "last name": [{"value": "Daniels", "modifier": ""}],
    "email": [{"value": "jack@example.com", "modifier": "work"}],
    "phone": [{"value": "555-1234", "modifier": "mobile"}]
  },
  "tags": "tag1,tag2",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

| Parameter     | Required | Description |
|---------------|----------|-------------|
| `record_type` | Yes      | `person` or `company` |
| `fields`      | Yes      | Dict of field names -> array of {value, modifier} objects. Minimum: name fields |
| `tags`        | No       | Comma-separated tags (max 5 on creation). Escape commas in tag names with backslash |
| `avatar_url`  | No       | URL to avatar image (lazy loaded, no validation) |

**Response:** `201 Created` -- Full contact object with ID, timestamps, fields, tags.

### 2.6 Create Company
```
POST /api/v1/contact
```
Same as 2.5 but with `"record_type": "company"`.

There is also an alternative endpoint observed in the Endgrate article:
```
POST /api/v1/companies
```
(May be an alias or newer endpoint variant.)

### 2.7 Update Contact
```
PUT /api/v1/contact/<contact_id>
```
**Query Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `replace` | 0       | `1` = replace all values of field type; `0` = merge with existing (update matching modifiers) |

**Request Body:**
```json
{
  "fields": {
    "email": [{"value": "new@example.com", "modifier": "work"}]
  },
  "avatar_url": "https://example.com/new-avatar.jpg"
}
```
At least one of `fields` or `avatar_url` must be provided.
Set field value to `null` to remove all values for that field.

**Response:** Updated contact object.

**Errors:** Validation Error, Quota Error, NotFound Error.

### 2.8 Delete Contact(s) -- Simple
```
DELETE /api/v1/contact/<id1>,<id2>,<id3>
```
Comma-separated contact IDs in URL path.

**Response:**
```json
{
  "status": "ok",
  "data": {
    "ids": ["<id1>", "<id2>", "<id3>"]
  }
}
```

### 2.9 Delete Contacts -- Advanced (Bulk)
```
DELETE /api/v1/contacts/list
```
**Query Parameters:**

| Parameter     | Default | Description |
|---------------|---------|-------------|
| `keyword`     | -       | Delete contacts matching keyword search |
| `record_type` | `all`   | `person` or `company` |
| `query`       | -       | Advanced search JSON for deletion |
| `limit`       | all     | Max number of contacts to delete |

Note: `query` and `keyword` are mutually exclusive. If `query` is present, `record_type` is ignored.

**Response:** Same format as 2.8.

---

## 3. CONTACT NOTES

### 3.1 List Notes for Contact
```
GET /api/v1/contact/<contact_id>/notes
```
**Query Parameters:**

| Parameter  | Default | Description |
|------------|---------|-------------|
| `per_page` | 5       | Items per page |
| `page`     | 1       | Page number |

**Response:**
```json
{
  "meta": {
    "per_page": 5,
    "total": 10,
    "pages": 2,
    "page": 1
  },
  "resources": [
    {
      "id": "...",
      "created": "2013-04-04T13:50:00+00:00",
      "contacts": [ /* abbreviated contact data */ ],
      "note_preview": "Plain text preview",
      "note": "<p>HTML formatted note</p>",
      "author_name": "John Doe",
      "owner_id": "..."
    }
  ]
}
```

### 3.2 Get Single Note
```
GET /api/v1/contacts/notes/<note_id>
```
**Response:** Single note object (same fields as in 3.1 resources).

**Errors:** Validation Error, NotFound Error.

### 3.3 Create Note
```
POST /api/v1/contacts/notes
```
**Request Body (all required):**
```json
{
  "contact_ids": ["<id1>", "<id2>"],
  "note": "Full note text with HTML",
  "note_preview": "Short plain text preview"
}
```

| Parameter      | Type   | Description |
|----------------|--------|-------------|
| `contact_ids`  | Array  | 1-10 contact IDs (BSON format) |
| `note`         | String | Full note content |
| `note_preview` | String | Short preview version |

**Response:** Created note object.

### 3.4 Update Note
```
PUT /api/v1/contacts/notes/<note_id>
```
**Request Body (all required):**
```json
{
  "contact_ids": ["<id1>", "<id2>"],
  "note": "Updated note text",
  "note_preview": "Updated preview"
}
```
Same parameters as 3.3.

**Response:** Updated note object.

**Errors:** Validation Error, NotFound Error.

### 3.5 Delete Note
```
DELETE /api/v1/contacts/notes/<note_id>
```
**Response:**
```json
{
  "id": "<note_id>"
}
```
**Errors:** Validation Error, NotFound Error.

---

## 4. CONTACT TAGS

### 4.1 Replace Contact Tags
```
PUT /api/v1/contacts/<contact_id>/tags
```
**IMPORTANT:** This is a full REPLACE operation. Tags not included in the request will be REMOVED from the contact.

**Request Body:**
```json
{
  "tags": ["Tag One", "Tag Two", "Tag Three"]
}
```

| Parameter | Type  | Description |
|-----------|-------|-------------|
| `tags`    | Array | List of tag strings. Tags not in this list will be removed |

**Response:** Empty JSON object `{}`

**Errors:** Validation Error.

---

## 5. CONTACTS METADATA (Custom Fields, Groups, Tabs, Choices)

### 5.1 List All Contact Fields Metadata
```
GET /api/v1/contacts/fields
```
**Parameters:** None

**Response:** Metadata structure containing all tabs, groups, and fields with their types, modifiers, and configuration.

### 5.2 Create Field
```
POST /api/v1/contacts/fields
```
**Request Body:**
```json
{
  "name": "My Custom Field",
  "field_type": {"field_kind": "string"},
  "presentation": {"number_type": "integer"},
  "group_id": "<group_id>",
  "tab_id": "<tab_id>",
  "insert_after": "<field_id_or_null>"
}
```

| Parameter      | Required | Description |
|----------------|----------|-------------|
| `name`         | Yes      | Unique field name |
| `field_type`   | Yes      | Dict describing field type (e.g., `{"field_kind": "string"}`) |
| `presentation` | Yes      | Dict for client display settings |
| `tab_id`       | Yes      | ID of tab this field belongs to |
| `group_id`     | No       | ID of group; can be null |
| `insert_after`  | No       | ID for positioning; null = first position |

**Response:** Fields metadata with the newly created field.

**Errors:** Validation Error, NotFound Error.

### 5.3 Update Field
```
PUT /api/v1/contacts/fields/<field_id>
```
**Request Body:**
```json
{
  "name": "Updated Field Name",
  "group_id": "<group_id>",
  "tab_id": "<tab_id>",
  "presentation": {},
  "insert_after": "<field_id_or_null>"
}
```

| Parameter      | Description |
|----------------|-------------|
| `name`         | New unique field name |
| `group_id`     | ID of fields group |
| `tab_id`       | ID of fields tab |
| `presentation` | Display config dict (can be empty) |
| `insert_after` | Position after this ID; null = first |

**Response:** Updated fields metadata.

**Errors:** Validation Error, NotFound Error.

### 5.4 Delete Field
```
DELETE /api/v1/contacts/fields/<field_id>
```
**Note:** Only custom fields can be deleted.

**Request Body (optional):**
```json
{
  "preflight_checks": true
}
```
`preflight_checks` = verify if field has values across contacts before deleting.

**Response:** Empty response, HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.5 Create Group
```
POST /api/v1/contacts/fields/groups
```
**Request Body (all required):**
```json
{
  "name": "My Group",
  "insert_after": "<group_or_field_id_or_null>",
  "logo_id": "<logo_id>",
  "tab_id": "<tab_id>"
}
```

**Response:** Fields metadata with newly created group.

### 5.6 Update Group
```
PUT /api/v1/contacts/fields/groups/<group_id>
```
**Request Body:**
```json
{
  "name": "Updated Group",
  "insert_after": "<id_or_null>",
  "logo_id": "<logo_id>",
  "tab_id": "<tab_id>"
}
```

**Response:** HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.7 Delete Group
```
DELETE /api/v1/contacts/fields/groups/<group_id>
```
**Note:** Only custom groups can be deleted.

**Request Body (optional):**
```json
{
  "preflight_checks": true
}
```

**Response:** Empty response, HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.8 Create Tab
```
POST /api/v1/contacts/fields/tabs
```
**Request Body (all required):**
```json
{
  "tab_name": "My Tab",
  "insert_after": "<tab_id_or_null>",
  "contact_types": ["person", "company"]
}
```

| Parameter       | Description |
|-----------------|-------------|
| `tab_name`      | Name for the new tab |
| `insert_after`  | Tab ID for positioning; null = first |
| `contact_types` | Array of `"person"` and/or `"company"` |

**Response:** Fields metadata with newly created tab.

### 5.9 Update Tab
```
PUT /api/v1/contacts/fields/tabs/<tab_id>
```
**Request Body:**
```json
{
  "tab_name": "Updated Tab",
  "insert_after": "<tab_id_or_null>",
  "contact_types": ["person"]
}
```

**Response:** HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.10 Delete Tab
```
DELETE /api/v1/contacts/tabs/<tab_id>
```
**Request Body (optional):**
```json
{
  "preflight_checks": true
}
```

**Response:** Empty response, HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.11 Create Choice (for dropdown/select fields)
```
POST /api/v1/contacts/fields/<field_id>/choices
```
**Request Body:**
```json
{
  "id": "unique_choice_id",
  "value": "Choice Label",
  "insert_after": "<choice_id_or_null>"
}
```

| Parameter      | Description |
|----------------|-------------|
| `id`           | Unique ID among field choices |
| `value`        | Display value for the choice |
| `insert_after` | Position after this choice ID; null = first |

**Response:** HTTP 200.

**Errors:** Validation Error, NotFound Error.

### 5.12 Delete Choice
```
DELETE /api/v1/contacts/fields/<field_id>/choices/<choice_id>
```
**Request Body (optional):**
```json
{
  "preflight_checks": true
}
```

**Response:** Empty response, HTTP 200.

**Errors:** Validation Error, NotFound Error.

---

## 6. TASKS

### 6.1 Create Task
```
POST /api/v1/activities/task
```
**Request Body:**
```json
{
  "subject": "Follow up with client",
  "notes": "Discuss renewal terms",
  "related_to": ["<contact_id1>", "<contact_id2>"],
  "due_date": "2026-04-01T10:00:00"
}
```

| Parameter    | Required | Description |
|--------------|----------|-------------|
| `subject`    | Yes      | Task title (2-128 chars) |
| `notes`      | No       | Additional task notes |
| `related_to` | No       | Array of contact IDs to associate |
| `due_date`   | No       | Due date in format `YYYY-MM-DDTHH:MM:SS` |

**Response:** Created task object:
```json
{
  "id": "...",
  "subject": "Follow up with client",
  "notes": "Discuss renewal terms",
  "due_date": "2026-04-01T10:00:00",
  "created": "...",
  "updated": "...",
  "assigned_to": { /* user object */ },
  "owner": "...",
  "owner_id": "...",
  "related_to": ["<contact_id1>"],
  "related": { /* contacts and deal relationships */ },
  "completed": false,
  "is_important": false,
  "starred": false,
  "comments": [],
  "tags": [],
  "company_id": "..."
}
```

**Errors:** Validation Error.

---

## 7. DEALS (API expanded in 2024-2025)

**Note:** The Deals API is documented at nimble.com/developers/docs (behind Cloudflare, not fully scrapable). The information below is compiled from Nimble support articles, blog posts, and third-party integrations. Exact URL paths follow the same patterns as contacts where documented.

### Documented Operations (from support.nimble.com/en/articles/502755):

| Operation | Description |
|-----------|-------------|
| **List all user's deals** | Retrieve all deals for the authenticated user |
| **Create deal** | Create a new deal |
| **Delete deal** | Delete an existing deal |
| **Add and update Tags** | Manage deal tags |
| **List Deal standard and pipeline Fields** | Get deal metadata/fields |
| **Create Deal Pipeline** | Create a new pipeline |
| **Update Deal Pipeline** | Modify an existing pipeline |
| **Delete Deal Pipeline** | Remove a pipeline |
| **List pipeline deals by stage and/or owners** | Filter deals by pipeline stage or owner |
| **Add custom deal fields** | Create custom fields on deals |
| **Update custom deal fields** | Modify custom deal fields |
| **Delete custom deal fields** | Remove custom deal fields |
| **List deals' overdue activities** | Get overdue activities for deals |

### Inferred Endpoint Paths (based on API naming patterns):

```
GET    /api/v1/deals                              -- List all deals
GET    /api/v1/deals/ids                           -- List deal IDs only
GET    /api/v1/deal/<deal_id>                      -- Get single deal
POST   /api/v1/deal                                -- Create deal
PUT    /api/v1/deal/<deal_id>                      -- Update deal
DELETE /api/v1/deal/<deal_id>                       -- Delete deal

GET    /api/v1/deals/fields                        -- List deal fields metadata
POST   /api/v1/deals/fields                        -- Create custom deal field
PUT    /api/v1/deals/fields/<field_id>             -- Update custom deal field
DELETE /api/v1/deals/fields/<field_id>              -- Delete custom deal field

GET    /api/v1/deals/pipelines                     -- List pipelines
POST   /api/v1/deals/pipelines                     -- Create pipeline
PUT    /api/v1/deals/pipelines/<pipeline_id>       -- Update pipeline
DELETE /api/v1/deals/pipelines/<pipeline_id>        -- Delete pipeline

GET    /api/v1/deals/overdue-activities             -- List overdue deal activities
```

### Deal Fields (from support.nimble.com):
- Deal name
- Description
- Amount
- Probability
- Expected close date
- Stage
- Pipeline
- Related contacts
- Tags
- Custom fields
- Files
- Notes

### Deal Request Body (inferred from contact pattern):
```json
{
  "fields": {
    "deal name": [{"value": "Enterprise Deal"}],
    "amount": [{"value": "50000"}],
    "stage": [{"value": "Proposal"}],
    "probability": [{"value": "75"}],
    "expected close date": [{"value": "2026-06-01"}],
    "description": [{"value": "Major enterprise opportunity"}]
  },
  "tags": "enterprise,high-priority",
  "pipeline_id": "<pipeline_id>"
}
```

**Important:** The deals metadata schema is stated to follow the same pattern as contacts metadata. Same field_type/presentation structure.

---

## 8. MESSAGES (mentioned in docs overview, limited info)

The API docs overview mentions Messages as a top-level category:
- Reading messages
- Creating draft messages

No specific endpoint paths were available from scrapable sources. These likely follow the pattern:
```
GET  /api/v1/messages                    -- List messages
POST /api/v1/messages/drafts             -- Create draft message
```

---

## COMMON RESPONSE PATTERNS

### Success Responses
- `200 OK` -- Standard success for GET, PUT, DELETE
- `201 Created` -- For POST (create) operations

### Error Responses

**Validation Error:**
```json
{
  "message": "Validation error description",
  "code": 245
}
```

**Quota Error:**
Returned when contact/deal creation quota is exceeded.

**NotFound Error:**
Returned when referenced ID does not exist.

### Pagination
Standard across all list endpoints:
```json
{
  "meta": {
    "page": 1,
    "pages": 5,
    "per_page": 30,
    "total": 150
  },
  "resources": []
}
```

### Contact Object Structure
```json
{
  "id": "5049f697a694620a0700007f",
  "created": "2012-09-07T16:32:08+03:00",
  "updated": "2012-09-07T16:32:08+03:00",
  "object_type": "contact",
  "record_type": "person",
  "creator": "...",
  "owner_id": "...",
  "tags": [
    {"id": "...", "tag": "Tag Name"}
  ],
  "fields": {
    "first name": [{"value": "Jack", "modifier": "", "label": "first name"}],
    "last name": [{"value": "Daniels", "modifier": "", "label": "last name"}],
    "email": [{"value": "jack@example.com", "modifier": "work", "label": "email"}]
  },
  "last_contacted": { /* contact activity info */ },
  "children": []
}
```

### Note Object Structure
```json
{
  "id": "...",
  "created": "2012-11-29T15:32:12+0000",
  "contacts": [ /* abbreviated contact data */ ],
  "note_preview": "Plain text note preview",
  "note": "<p>HTML formatted note content</p>",
  "author_name": "User Name",
  "owner_id": "..."
}
```

---

## DEFAULT CONTACT FIELDS REFERENCE

### Simple Text Fields
- `first name`, `last name`, `middle name`
- `company name`
- `title` (deprecated)
- `skype id`
- `hubspot`
- `annual revenue`
- `birthday`

### Multi-Value Fields with Modifiers
- `phone` -- modifiers: work, home, mobile, main, home fax, work fax, other
- `email` -- modifiers: work, personal, other
- `URL` -- modifiers: work, personal, blog, other
- `description` -- modifiers: other, twitter, facebook, linkedin, google+, foursquare

### Social Fields
- `twitter`, `facebook`, `linkedin`, `google+`, `foursquare`

### Complex Fields
- `address` -- dict: `{street, city, state, zip, country}`
- `contact employment` -- dict: `{company_name, title, start_date, end_date, is_present}`
- `domain` -- unique, company records only
- `parent company` (deprecated; use contact employment)

### Dropdown/Choice Fields
- `# of employees`
- `lead status`
- `rating`
- `lead source`
- `lead type`

### Special Fields
- User type field -- contains Nimble user ID

### Default Tabs
1. Personal Info
2. Company Info
3. Contact Info
4. Lead Details
5. Additional Lead Fields

---

## COMPLETE ENDPOINT SUMMARY TABLE

| # | Method | Path | Description | Source |
|---|--------|------|-------------|--------|
| 1 | GET | `/api/v1/myself` | Get current user info | Verified (support docs, Pipedream) |
| 2 | GET | `/api/v1/contacts` | List contacts (with search) | Verified (readthedocs) |
| 3 | GET | `/api/v1/contacts/ids` | List contact IDs only | Verified (readthedocs) |
| 4 | GET | `/api/v1/contact/<id>` | Get contact by ID | Verified (readthedocs) |
| 5 | POST | `/api/v1/contact` | Create contact | Verified (readthedocs, Pipedream) |
| 6 | PUT | `/api/v1/contact/<id>` | Update contact | Verified (readthedocs, Pipedream) |
| 7 | DELETE | `/api/v1/contact/<id>,<id>` | Delete contact(s) | Verified (readthedocs) |
| 8 | DELETE | `/api/v1/contacts/list` | Bulk delete contacts | Verified (readthedocs) |
| 9 | GET | `/api/v1/contact/<id>/notes` | List notes for contact | Verified (readthedocs) |
| 10 | GET | `/api/v1/contacts/notes/<note_id>` | Get single note | Verified (readthedocs) |
| 11 | POST | `/api/v1/contacts/notes` | Create note | Verified (readthedocs) |
| 12 | PUT | `/api/v1/contacts/notes/<note_id>` | Update note | Verified (readthedocs) |
| 13 | DELETE | `/api/v1/contacts/notes/<note_id>` | Delete note | Verified (readthedocs) |
| 14 | PUT | `/api/v1/contacts/<id>/tags` | Replace contact tags | Verified (readthedocs) |
| 15 | GET | `/api/v1/contacts/fields` | List all contact fields metadata | Verified (readthedocs) |
| 16 | POST | `/api/v1/contacts/fields` | Create custom field | Verified (readthedocs) |
| 17 | PUT | `/api/v1/contacts/fields/<field_id>` | Update custom field | Verified (readthedocs) |
| 18 | DELETE | `/api/v1/contacts/fields/<field_id>` | Delete custom field | Verified (readthedocs) |
| 19 | POST | `/api/v1/contacts/fields/groups` | Create field group | Verified (readthedocs) |
| 20 | PUT | `/api/v1/contacts/fields/groups/<group_id>` | Update field group | Verified (readthedocs) |
| 21 | DELETE | `/api/v1/contacts/fields/groups/<group_id>` | Delete field group | Verified (readthedocs) |
| 22 | POST | `/api/v1/contacts/fields/tabs` | Create field tab | Verified (readthedocs) |
| 23 | PUT | `/api/v1/contacts/fields/tabs/<tab_id>` | Update field tab | Verified (readthedocs) |
| 24 | DELETE | `/api/v1/contacts/tabs/<tab_id>` | Delete field tab | Verified (readthedocs) |
| 25 | POST | `/api/v1/contacts/fields/<field_id>/choices` | Create choice for dropdown | Verified (readthedocs) |
| 26 | DELETE | `/api/v1/contacts/fields/<field_id>/choices/<choice_id>` | Delete choice | Verified (readthedocs) |
| 27 | POST | `/api/v1/activities/task` | Create task | Verified (readthedocs, Pipedream) |
| 28 | GET | `/api/v1/deals` | List all deals | Inferred (support docs) |
| 29 | POST | `/api/v1/deal` | Create deal | Inferred (support docs) |
| 30 | PUT | `/api/v1/deal/<deal_id>` | Update deal | Inferred (support docs) |
| 31 | DELETE | `/api/v1/deal/<deal_id>` | Delete deal | Inferred (support docs) |
| 32 | GET | `/api/v1/deals/fields` | List deal fields metadata | Inferred (support docs -- "same schema as contacts") |
| 33 | POST | `/api/v1/deals/fields` | Create custom deal field | Inferred (support docs) |
| 34 | PUT | `/api/v1/deals/fields/<field_id>` | Update custom deal field | Inferred (support docs) |
| 35 | DELETE | `/api/v1/deals/fields/<field_id>` | Delete custom deal field | Inferred (support docs) |
| 36 | GET | `/api/v1/deals/pipelines` | List pipelines | Inferred (support docs) |
| 37 | POST | `/api/v1/deals/pipelines` | Create pipeline | Inferred (support docs) |
| 38 | PUT | `/api/v1/deals/pipelines/<pipeline_id>` | Update pipeline | Inferred (support docs) |
| 39 | DELETE | `/api/v1/deals/pipelines/<pipeline_id>` | Delete pipeline | Inferred (support docs) |
| 40 | GET | `/api/v1/deals/overdue-activities` | List overdue deal activities | Confirmed (support docs mention path) |

**Verification Legend:**
- **Verified** = Endpoint path confirmed in official readthedocs documentation or multiple independent sources
- **Inferred** = Operation confirmed to exist (support docs), path follows established API patterns
- **Confirmed** = Specific path mentioned in a Nimble source but full parameters not documented in scrapable sources