import re

PHONE = re.compile(r"\b\d{4}[\s-]?\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# Source бүрийн цэвэрлэгээний дүрэм.
#   list_drop / detail_drop — дээд түвшний талбарыг бүтнээр нь хасна
#   nested_drop             — гүн талбар, (эцэг, хүүхэд) хэлбэрээр
#   text_fields             — текст дотор утас, имэйл mask хийнэ
RULES = {
    "zangia": {
        "list_drop": ("contact", "search_description", "search_requirements",
                      "search_main", "logo", "is_featured", "changeable", "mlevel"),
        "detail_drop": ("contact", "similarJobs", "is_applicant", "logo",
                        "for_hbi", "for_hbi_type", "is_featured", "changeable",
                        "mentorshipProgram", "mlevel"),
        "nested_drop": (
            ("company", "emails"), ("company", "phone"),
            ("company", "header"), ("company", "banners"), ("company", "logo"),
            ("company", "mlevel"), ("company", "group_id"),
            ("company", "facebook"), ("company", "twitter"),
            ("company", "instagram"), ("company", "youtube"),
            ("company", "slogan"), ("company", "vision"),
            ("company", "mission"), ("company", "valuable"),
        ),
        "text_fields": ("description", "requirements", "additional"),
    },

    "worki": {
        "list_drop": (),
        "detail_drop": (),
        "nested_drop": (),
        "text_fields": ("responsibility", "description"),
    },

    "lambda": {
        "list_drop": (),
        "detail_drop": ("isApplied", "score", "gap", "jobApply"),
        "nested_drop": (
            ("recruiter", "phoneNumber"), ("recruiter", "firstName"),
            ("recruiter", "lastName"), ("recruiter", "picture"),
            ("recruiter", "cover"),
        ),
        "nested_text": (("recruiter", "bio"), ("recruiter", "comment")),
        "text_fields": ("description", "responsibilities", "instruction", "comment"),
    },
}


def _rules(source):
    return RULES.get(source, {})


def mask_text(value):
    if not isinstance(value, str):
        return value
    return EMAIL.sub("[email]", PHONE.sub("[phone]", value))


def _drop_nested(payload, path):
    node = payload
    for key in path[:-1]:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return
    if isinstance(node, dict):
        node.pop(path[-1], None)

def _mask_nested(payload, path):
    node = payload
    for key in path[:-1]:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return
    if isinstance(node, dict) and path[-1] in node:
        node[path[-1]] = mask_text(node[path[-1]])

def _clean(payload, source, drop_key):
    if not isinstance(payload, dict):
        return payload
    rules = _rules(source)
    for key in rules.get(drop_key, ()):
        payload.pop(key, None)
    for path in rules.get("nested_drop", ()):
        _drop_nested(payload, path)
    for path in rules.get("nested_text", ()):
        _mask_nested(payload, path)
    for field in rules.get("text_fields", ()):
        if field in payload:
            payload[field] = mask_text(payload[field])
    return payload


def clean_list(item, source):
    return _clean(item, source, "list_drop")


def clean_detail(detail, source):
    return _clean(detail, source, "detail_drop")