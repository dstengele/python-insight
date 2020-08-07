# API client for Jira Insight

This is a API client to access data in the Jira app [Insight](https://marketplace.atlassian.com/apps/1212137/insight-asset-management).

## Usage

```python
from jira_insight import *

# Initialize the main Insight object with the URL and credentials for Basic Auth
insight = Insight("https://jira.example.com", ("USERNAME", "PASSWORD"))
# Get a specific object schema by ID
object_schema = InsightObjectSchema(insight, 1)
# Search for objects by IQL
objects = object_schema.search_iql("SerialNumber = DEADBEEF")
```

## Caveats
* First and foremost: This is alpha software. I use it for a specific use case,
but for everything else, there be dragons.
* This is probably very slow with complex object schemas, as many things are
loaded preemptively when the Insight object is first instanciated.
* You can not yet edit objects after they have been created.
