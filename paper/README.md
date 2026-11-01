# Англоязычная научная статья

Статья «Nominal Price Rigidity, Capital Accumulation, and Monetary Policy Transmission» подготовлена **на английском языке**. Автор: **Pitti King**. Организация: **Bellmar Institute for Quantitative Economics**. Основной исходный документ: `paper/article.qmd`. Для вёрстки применяется встроенный формат **Quarto → Typst → PDF**; библиография — `paper/references.bib`.

Все таблицы и рисунки в статье выполнены на английском языке. Исходные данные для рисунков вычисляются в `src/experiment.py` и записываются в CSV под `results/`. Скрипт `paper/scripts/make_figures.py` независимо переводит эти результаты в англоязычные отдельные SVG-графики. `paper/scripts/check_results.py` проверяет ключевые значения таблиц по исходным CSV.

Для локального воспроизведения из корня проекта:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.audit
python -m src.experiment
python -m paper.scripts.check_results
python -m paper.scripts.make_figures
quarto render paper/article.qmd --to typst
```

GitHub Actions выполняет те же проверки, затем компилирует `paper/article.pdf` с помощью Typst. Успешная сборка сохраняется как артефакт выполнения, а при запуске из `main` итоговый PDF записывается коммитом непосредственно в репозиторий. Запросы на объединение выполняют проверку сборки, не публикуя PDF в `main` до объединения.

**Граница результата:** расчёты относятся к демонстрационной калибровке и линейному рационально-ожидаемому равновесию первого порядка. Они не являются эконометрическими оценками или расчётами оптимального благосостояния.
