# Article for Overleaf (academic journal)

Elsevier `elsarticle` from the [Academic journal](https://www.overleaf.com/latex/templates/tagged/academic-journal) gallery. The text is in **English**.

## How to open

1. On [Overleaf](https://www.overleaf.com): New Project → Upload Project.
2. Upload a zip of the `paper/` folder (`main.tex`, `references.bib`, and `screenshots/`).
3. Compiler: **pdfLaTeX**, main file: `main.tex`.
4. Recompile. Bibliography is pulled in via BibTeX.

The UI figures are PNGs under `screenshots/`. If they are missing, Overleaf will fail on `\includegraphics`.

## Files

| File | Role |
|------|------|
| `main.tex` | article (English) |
| `references.bib` | bibliography |
| `screenshots/01_ui_query_crop.png` | Fig. Streamlit query |
| `screenshots/02_ui_results.png` | Fig. analog table |
| `screenshots/03_ui_steps.png` | Fig. LangGraph steps |

Fix the author name and affiliation in `\author` / `\affiliation` before submission.
