import asyncio
import os
import random
import re
from pathlib import Path
from docx import Document
import fitz
from PIL import Image
from playwright.async_api import async_playwright
import pytesseract

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"

FINAL_DOCX_PATH = OUTPUT_DIR / "Full_Book.docx"
FINAL_TXT_PATH = OUTPUT_DIR / "Full_Book.txt"
FINAL_PDF_PATH = OUTPUT_DIR / "Full_Book.pdf"

START_PARSING = False

DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(DEFAULT_TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_PATH

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def convert_svg_to_png(svg_data: bytes, png_path: Path, scale: float = 3.0) -> bool:
    try:
        doc = fitz.open(stream=svg_data, filetype="svg")
        page = doc[0]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(png_path))
        return True
    except Exception as e:
        print(f"[ОШИБКА] Конвертация SVG: {e}")
        return False


def ocr_and_clean(png_path: Path) -> str:
    try:
        raw_text = pytesseract.image_to_string(
            Image.open(png_path), lang="rus+eng"
        )
        text = re.sub(r"(\w+)\s*[-—:\u00AD]\s*\n\s*(\w+)", r"\1\2", raw_text)
        text = re.sub(r"\n\s*\n", "[[PARAGRAPH]]", text)
        text = re.sub(r"\n", " ", text)
        text = text.replace("[[PARAGRAPH]]", "\n\n")
        text = re.sub(r" +", " ", text)
        return text.strip()
    except Exception as e:
        print(f"[ОШИБКА] OCR: {e}")
        return ""


def append_page_to_txt(page_num: int, text: str):
    with open(FINAL_TXT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n=== СТРАНИЦА {page_num} ===\n\n")
        f.write(text)


def add_page_to_docx(doc, page_num: int, text: str):
    doc.add_heading(f"Страница {page_num}", level=2)
    for paragraph in text.split("\n\n"):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())
    doc.add_page_break()
    doc.save(str(FINAL_DOCX_PATH))


def convert_docx_to_pdf():
    if not FINAL_DOCX_PATH.exists():
        return

    print("\n[СБОРКА] Формирование итогового PDF файла...")
    doc = Document(str(FINAL_DOCX_PATH))
    pdf_doc = fitz.open()

    current_page_text = []
    page_counter = 1

    for p in doc.paragraphs:
        if p.text.startswith("Страница "):
            if current_page_text:
                pdf_page = pdf_doc.new_page(width=595, height=842)
                html_content = f"<h3>Страница {page_counter}</h3>" + "".join(
                    f"<p>{txt}</p>" for txt in current_page_text
                )
                pdf_page.insert_htmlbox(
                    fitz.Rect(40, 40, 555, 802), html_content
                )
                current_page_text = []
                page_counter += 1
        else:
            if p.text.strip():
                current_page_text.append(p.text.strip())

    if current_page_text:
        pdf_page = pdf_doc.new_page(width=595, height=842)
        html_content = f"<h3>Страница {page_counter}</h3>" + "".join(
            f"<p>{txt}</p>" for txt in current_page_text
        )
        pdf_page.insert_htmlbox(fitz.Rect(40, 40, 555, 802), html_content)

    pdf_doc.save(str(FINAL_PDF_PATH))
    print(f"[УСПЕХ] Итоговый PDF сохранен: {FINAL_PDF_PATH}")


async def main():
    global START_PARSING

    target_url = input("Вставьте ссылку на книгу: ").strip()
    max_pages = int(
        input("Сколько страниц выгрузить? (по умолчанию 500): ") or "500"
    )

    seen_svg_hashes = set()
    page_counter = 0

    if FINAL_TXT_PATH.exists():
        os.remove(FINAL_TXT_PATH)
    if FINAL_DOCX_PATH.exists():
        os.remove(FINAL_DOCX_PATH)

    docx_doc = Document()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        async def handle_response(response):
            nonlocal page_counter

            if not START_PARSING or page.is_closed():
                return

            url = response.url
            if ".svg" in url or "page" in url or "viewer" in url:
                try:
                    body = await response.body()

                    if (
                        len(body) > 15000
                        and b"<svg" in body[:200]
                        and b"font_" in body
                    ):
                        body_hash = hash(body)
                        if body_hash in seen_svg_hashes:
                            return
                        seen_svg_hashes.add(body_hash)

                        page_counter += 1
                        current_page = page_counter
                        print(
                            f"\n[Страница {current_page}] Загружено ({len(body)} байт)..."
                        )

                        temp_png = OUTPUT_DIR / f"temp_{current_page}.png"

                        if convert_svg_to_png(body, temp_png):
                            text = ocr_and_clean(temp_png)

                            if len(text) > 50:
                                append_page_to_txt(current_page, text)
                                add_page_to_docx(docx_doc, current_page, text)
                                print(
                                    f"[УСПЕХ] Страница {current_page} сохранена ({len(text)} символов)."
                                )

                            if temp_png.exists():
                                os.remove(temp_png)
                except Exception:
                    pass

        page.on("response", handle_response)

        print("\nОткрываем браузер...")
        await page.goto(target_url)

        print("\n--- ИНСТРУКЦИЯ ---")
        print("1. Авторизуйтесь в аккаунте в открывшемся окне браузера.")
        print("2. Перейдите на стартовую страницу для начала выгрузки.")
        input("\nГотовы? Нажмите ENTER в этой консоли...")

        START_PARSING = True
        print(f"\nЗапуск парсинга ({max_pages} страниц)...\n")

        for i in range(max_pages):
            print(f"Продвижение вперед ({i+1}/{max_pages})...", end="\r")

            try:
                for _ in range(3):
                    await page.mouse.wheel(0, 800)
                    await asyncio.sleep(0.2)

                viewport = page.viewport_size
                if viewport:
                    w, h = viewport["width"], viewport["height"]
                    await page.mouse.click(int(w * 0.95), int(h * 0.5))

                await page.keyboard.press("PageDown")
                await asyncio.sleep(0.2)
                await page.keyboard.press("ArrowRight")

            except Exception:
                pass

            await asyncio.sleep(3.5 + random.uniform(0.3, 0.7))

        await browser.close()

    print("\nПролистывание завершено!")
    convert_docx_to_pdf()


if __name__ == "__main__":
    asyncio.run(main())
