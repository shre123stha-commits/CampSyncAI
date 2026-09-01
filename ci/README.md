# CI

`github-actions-ci.yml` is the GitHub Actions workflow for this project.

It could not be committed to `.github/workflows/` automatically because the
authoring app lacks the `workflows` permission. To activate it:

```bash
mkdir -p .github/workflows
git mv ci/github-actions-ci.yml .github/workflows/ci.yml
git commit -m "ci: enable GitHub Actions"
git push
```

It runs `ruff` and the full pytest suite on Python 3.12. No Ollama is
required — every test stubs the LLM.
