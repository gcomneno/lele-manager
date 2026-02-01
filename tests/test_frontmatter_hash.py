from lele_manager.cli.import_from_dir import compute_frontmatter_hash

def test_frontmatter_hash_is_stable_across_key_order() -> None:
    fm1 = {"id": "x/1", "topic": "python", "source": "note", "importance": 3, "tags": ["a", "b"]}
    fm2 = {"source": "note", "tags": ["a", "b"], "importance": 3, "topic": "python", "id": "x/1"}
    assert compute_frontmatter_hash(fm1) == compute_frontmatter_hash(fm2)
