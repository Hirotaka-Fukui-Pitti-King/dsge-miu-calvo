# Научная статья и воспроизводимая сборка

Исходный документ: `article.qmd`. Основной формат: Quarto → Typst → PDF. Библиографические записи находятся в `references.bib`. Рисунки создаются в каталоге `figures/` и перед сборкой копируются в `paper/assets/` для соблюдения ограничений Typst на доступ к файлам.

Порядок локального воспроизведения из корня репозитория:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.audit
python -m src.experiment
python -m paper.scripts.check_results
New-Item -ItemType Directory -Force paper/assets | Out-Null
Copy-Item figures/technology_vypusk.svg, figures/monetary_vypusk.svg, figures/monetary_investicii.svg, figures/monetary_potreblenie.svg paper/assets/
quarto render paper/article.qmd --to typst
```

Для сборки требуется Quarto с поддержкой Typst и шрифт `DejaVu Serif`. В GitHub Actions это устанавливается автоматически. Файл `paper/article.pdf` публикуется в артефактах выполнения «Сборка научной статьи» под именем `statya-dsge-typst`. Если сборка не прошла, нельзя считать PDF проверенным.

**Ограничение:** приведённые числа относятся к иллюстративной калибровке и аппроксимации первого порядка. Статья не предъявляет их как эмпирические оценки.
