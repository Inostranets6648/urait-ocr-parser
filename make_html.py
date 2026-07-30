import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"

TXT_PATH = OUTPUT_DIR / "Full_Book.txt"
HTML_OUTPUT_PATH = OUTPUT_DIR / "Full_Book.html"


def is_garbage_line(line: str) -> bool:
    line_str = line.strip()
    if not line_str:
        return True

    if len(line_str) <= 3 and not line_str.isalnum():
        return True

    letters_count = len(re.findall(r"[a-zA-Zа-яА-ЯёЁ]", line_str))
    if len(line_str) > 5 and (letters_count / len(line_str)) < 0.4:
        return True

    if re.match(r"^(Рис|Схема|Таблица)\s*\d+[\.\s]*$", line_str, re.IGNORECASE):
        return True

    return False


def clean_ocr_text(raw_text: str) -> str:
    cleaned_lines = []
    for line in raw_text.split("\n"):
        if not is_garbage_line(line):
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def txt_to_readable_html():
    if not TXT_PATH.exists():
        print(f"[ОШИБКА] Файл {TXT_PATH} не найден!")
        return

    print("Считывание и очистка текста...")
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    cleaned_text = clean_ocr_text(raw_text)

    text = re.sub(
        r"=== СТРАНИЦА (\d+) ===",
        r'</div><div class="page" id="page-\1"><div class="page-number">Страница \1</div>',
        cleaned_text,
    )

    text = re.sub(
        r"((?:Тема|Глава)\s+\d+.*?)(?=\n)",
        r'<h2 class="chapter-title">\1</h2>',
        text,
    )

    text = re.sub(
        r"(\d+\.\d+\.\s+[^\n]+)",
        r'<h3 class="section-title">\1</h3>',
        text,
    )

    paragraphs = text.split("\n\n")
    formatted_html = []

    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        if (
            p_strip.startswith("<h2")
            or p_strip.startswith("<h3")
            or p_strip.startswith('<div class="page"')
        ):
            formatted_html.append(p_strip)
        else:
            p_clean = p_strip.replace("\n", " ")
            formatted_html.append(f"<p>{p_clean}</p>")

    body_content = "\n".join(formatted_html)

    html_template = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Электронный ридер</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Georgia, serif;
            line-height: 1.8;
            color: #2c3e50;
            background-color: #f4f6f8;
            margin: 0;
            padding: 20px;
        }}
        .reader-container {{
            max-width: 800px;
            margin: 0 auto;
            background: #ffffff;
            padding: 40px 60px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border-radius: 8px;
        }}
        .page {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px dashed #e0e6ed;
        }}
        .page-number {{
            display: inline-block;
            background: #eef2f7;
            color: #5a6b7c;
            padding: 2px 10px;
            font-size: 0.85em;
            font-weight: bold;
            border-radius: 4px;
            margin-bottom: 20px;
        }}
        h2.chapter-title {{
            color: #1a365d;
            border-bottom: 2px solid #3182ce;
            padding-bottom: 8px;
            margin-top: 30px;
            font-size: 1.6em;
        }}
        h3.section-title {{
            color: #2b6cb0;
            margin-top: 25px;
            font-size: 1.3em;
        }}
        p {{
            text-align: justify;
            text-justify: inter-word;
            margin-bottom: 1.2em;
            font-size: 1.05em;
        }}
        @media (max-width: 600px) {{
            .reader-container {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="reader-container">
        {body_content}
    </div>
</body>
</html>
"""

    with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"[УСПЕХ] Готовый интерактивный ридер сохранен: {HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    txt_to_readable_html()
