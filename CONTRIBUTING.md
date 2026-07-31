# Contributing to LeLe Manager

[English](CONTRIBUTING.md) | [Italiano](CONTRIBUTING.it.md)

Thank you for your interest. This project accepts code, test, documentation,
and bug-report contributions.

## Local development quick start

Requirements:

- a Python version supported by the project; see `pyproject.toml`;
- `git`.

Typical setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

## Quality gates

Before opening a pull request, run:

```bash
ruff check .
mypy src/lele_manager
pytest
```

Frontend or GUI changes may also require:

```bash
./scripts/build-gui.sh
cd frontend
npm install
npm run test:e2e
```

Use the smallest relevant validation set while developing, then run the full
required gates before publishing the final revision.

## Contribution types

- Bug fixes should include a reproducing test when practical.
- New features should remain focused; open an issue first when design alignment
  is useful.
- Documentation changes should improve clarity, examples, navigation, or
  troubleshooting without altering technical meaning accidentally.
- Test and CI changes should improve coverage or reliability without adding
  unnecessary infrastructure.

## Issues and pull requests

A useful issue includes:

- expected behavior;
- observed behavior;
- minimal reproduction steps, commands, or input;
- operating system and Python version when relevant.

Pull requests should:

- address one coherent concern;
- explain why the change is needed, not only what changed;
- update or add tests when appropriate;
- update API, CLI, or user documentation when behavior changes;
- avoid unrelated mass refactors.

## Bilingual documentation

English is the canonical documentation language. Italian mirrors are
officially maintained for the pairs declared in
[`docs/documentation-policy.md`](docs/documentation-policy.md).

When a pull request changes a bilingual canonical document:

- evaluate the Italian mirror in the same pull request;
- update both versions when requirements, examples, warnings, limitations, or
  technical meaning change;
- preserve reciprocal language links;
- keep commands, options, endpoints, symbols, paths, filenames, and snippets
  unchanged;
- run:

```bash
pytest tests/test_documentation.py
```

Historical, generated, internal, and English-only technical documents are
excluded only as declared in the documentation policy.

## Style and compatibility

- Follow the style already used in the affected area.
- Avoid broad refactors inside small bug fixes.
- Prefer explicit names and small functions.
- Do not commit secrets, credentials, personal vault data, datasets, or models.
- Preserve supported Python and frontend toolchain compatibility.

## Licensing

By contributing, you agree that your contribution is released under the same
license as the project.
