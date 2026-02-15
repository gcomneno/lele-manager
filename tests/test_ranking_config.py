from lele_manager.core.ranking import RankingConfig, SimilarityRankingConfig


def test_ranking_config_defaults_match_current_behavior() -> None:
    cfg = RankingConfig.default()
    assert isinstance(cfg.similarity, SimilarityRankingConfig)
    assert cfg.similarity.top_k_default == 5
    assert cfg.similarity.min_score_default == 0.0
    assert cfg.similarity.argsort_kind is None
    assert cfg.similarity.tiebreaker == "none"


def test_ranking_config_serialization_is_jsonable() -> None:
    cfg = RankingConfig.default()
    d = cfg.to_dict()
    assert d["similarity"]["top_k_default"] == 5
    assert d["similarity"]["min_score_default"] == 0.0
    assert d["similarity"]["argsort_kind"] is None
