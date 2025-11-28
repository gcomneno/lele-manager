source .venv/bin/activate

# 1) Import dal vault (se non l’hai già fatto oggi)
python -m lele_manager.cli.import_from_dir \
  ~/LeLeVault \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter

# 2) Training topic model
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite

# 3) Similarità
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "Quando uso std::cin >> su una string, l'input viene troncato agli spazi" \
  --top-k 5 \
  --min-score 0.1
