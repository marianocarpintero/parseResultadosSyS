import pdfplumber
import sys

pdf_path = sys.argv[1]

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages, start=1):
        txt = page.extract_text() or ""
        print("\n" + "="*60)
        print(f"PAGE {i} / {len(pdf.pages)}")
        print("="*60)
        print(txt)