from pathlib import Path
from xml.etree import ElementTree


BRAND_SVGS = (
    Path("frontend/public/brand/lele-manager-mark.svg"),
    Path("frontend/public/brand/lele-manager-lockup.svg"),
    Path("frontend/public/favicon.svg"),
)

FORBIDDEN_VALUE_FRAGMENTS = (
    "data:",
    "http://",
    "https://",
    "//",
    "file://",
    "/home/",
    "/users/",
    "c:\\users\\",
)


def test_brand_svgs_are_parseable_and_self_contained() -> None:
    for path in BRAND_SVGS:
        root = ElementTree.parse(path).getroot()
        assert root.tag.endswith("svg"), path

        for element in root.iter():
            tag_name = element.tag.rsplit("}", 1)[-1].lower()
            assert tag_name not in {"script", "image", "foreignobject"}, path
            for value in element.attrib.values():
                assert not any(fragment in value.lower() for fragment in FORBIDDEN_VALUE_FRAGMENTS), path


def test_lockup_source_contains_literal_product_name() -> None:
    lockup = Path("frontend/public/brand/lele-manager-lockup.svg").read_text(encoding="utf-8")
    assert "LeLe Manager" in lockup


def test_giadaware_monkey_asset_is_safe_and_local() -> None:
    from pathlib import Path
    from xml.etree import ElementTree as ET

    root = Path(__file__).resolve().parents[1]
    asset = (
        root
        / "frontend"
        / "public"
        / "brand"
        / "giadaware-monkey.svg"
    )

    assert asset.is_file()

    svg = ET.parse(asset).getroot()
    assert svg.tag.endswith("svg")

    title = None
    description = None

    forbidden_tags = {
        "script",
        "image",
        "foreignObject",
    }

    for element in svg.iter():
        tag = element.tag.rsplit("}", 1)[-1]

        assert tag not in forbidden_tags

        if tag == "title":
            title = (element.text or "").strip()
        elif tag == "desc":
            description = (element.text or "").strip()

        for value in element.attrib.values():
            lowered = value.lower()

            assert "https://" not in lowered
            assert "data:" not in lowered
            assert "javascript:" not in lowered

    assert title == "GiadaWare monkey mascot"
    assert description
