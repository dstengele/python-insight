ATTRIBUTE_TYPES = {
    0: {
        0: "Text",
        1: "Integer",
        2: "Boolean",
        3: "Double",
        4: "Date",
        5: "Time",
        6: "Date Time",
        7: "URL",
        8: "Email",
        9: "Textarea",
        10: "Select",
    },
    1: "Object",
    2: "User",
    3: "Confluence",
    4: "Group",
    5: "Version",
    6: "Project",
    7: "Status",
}


class InsightObjectTypeAttribute(object):
    def __init__(self, object_schema, object_type_attribute_json):
        self.insight = object_schema.insight
        self.object_schema = object_schema

        self.id = object_type_attribute_json["id"]
        self.name = object_type_attribute_json["name"]
        self.description = object_type_attribute_json.get("description", None)

        attribute_type_id = object_type_attribute_json["type"]
        default_type_id = object_type_attribute_json.get("defaultType", {}).get(
            "id", None
        )
        if attribute_type_id == 0:
            self.attribute_type = ATTRIBUTE_TYPES[0][default_type_id]
        else:
            self.attribute_type = ATTRIBUTE_TYPES[attribute_type_id]

    def __str__(self):
        return f"InsightObjectTypeAttribute: {self.name}"
