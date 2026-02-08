import reportlab.lib.utils
from io import BytesIO

# Monkeypatch for ReportLab 4.0 compatibility with older xhtml2pdf
if not hasattr(reportlab.lib.utils, 'getStringIO'):
    def getStringIO(data=None):
        if data is None:
            return BytesIO()
        if isinstance(data, str):
            return BytesIO(data.encode('utf-8'))
        return BytesIO(data)
    reportlab.lib.utils.getStringIO = getStringIO

from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader
import os

import markdown

class PDFGenerator:
    def __init__(self, template_dir: str | None = None):
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

    def generate_pdf(self, template_name: str, context: dict) -> BytesIO:
        """
        Generates a PDF from a Jinja2 template and context.
        Returns a BytesIO object containing the PDF data.
        """
        template = self.env.get_template(template_name)
        html_content = template.render(context)
        
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer
        )

        if pisa_status.err:
            raise Exception(f"PDF generation error: {pisa_status.err}")
        
        pdf_buffer.seek(0)
        return pdf_buffer

    def generate_resume_from_markdown(self, markdown_content: str, profile_data: dict) -> BytesIO:
        # Convert Markdown to HTML with hard line breaks for tighter formatting.
        html_body = markdown.markdown(markdown_content, extensions=["nl2br"])
        context = {
            "profile": profile_data,
            "body_content": html_body
        }
        return self.generate_pdf("resume_markdown.html", context)

    def generate_cover_letter(self, profile_data: dict, cover_letter_content: str, company_name: str, date: str) -> BytesIO:
        context = {
            "profile": profile_data,
            "cover_letter_content": cover_letter_content,
            "company_name": company_name,
            "date": date
        }
        return self.generate_pdf("cover_letter.html", context)
