import requests
import os

GROBID_URL = "http://localhost:8070/api/processFulltextDocument"

pdf_dir = "../data/pdfs"
xml_dir = "../data/xml"

os.makedirs(xml_dir, exist_ok=True)

for pdf in os.listdir(pdf_dir):
    with open(os.path.join(pdf_dir, pdf), 'rb') as f:
        files = {'input': f}
        r = requests.post(GROBID_URL, files=files)

    output_file = os.path.join(xml_dir, pdf.replace(".pdf",".xml"))

    with open(output_file, "w", encoding="utf-8") as out:
        out.write(r.text)