# Modernise old pythons
from __future__ import print_function, unicode_literals
import sys
PYTHON_3 = sys.version_info[0] == 3

if PYTHON_3:
    # Modern Python
    from io import BytesIO
    import chardet
else:    # Old Python
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter as PI
from pdfminer.layout import LAParams
from pdfminer.converter import TextConverter
# the internal API has changed between versions upstream,
# allow both here..
try:
    from pdfminer.pdfparser import PDFDocument
except ImportError:
    from pdfminer.pdfdocument import PDFDocument
try:
    from pdfminer.pdfparser import PDFPage
except ImportError:
    from pdfminer.pdfpage import PDFPage
from . import utils

__all__ = ['PDF']

class PDFPageInterpreter(PI):
    def process_page(self, page):
        if hasattr(self, 'debug'):
            if 1 <= self.debug:
                print(f"Processing page: {page}", file=sys.stderr)
        (x0,y0,x1,y1) = page.mediabox
        if page.rotate == 90:
            ctm = (0,-1,1,0, -y0,x1)
        elif page.rotate == 180:
            ctm = (-1,0,0,-1, x1,y1)
        elif page.rotate == 270:
            ctm = (0,1,-1,0, y1,-x0)
        else:
            ctm = (1,0,0,1, -x0,-y0)
        self.device.outfp.seek(0)
        self.device.outfp.truncate(0)
        self.device.begin_page(page, ctm)
        self.render_contents(page.resources, page.contents, ctm=ctm)
        self.device.end_page(page)
        return self.device.outfp.getvalue()

class PDF(list):
    def __init__(self, file, password='', just_text=1, check_extractable=True, char_margin=1.0, line_margin=0.1, word_margin=0.1):
        if sys.version_info.major > 2 and isinstance(password, str):
            password = password.encode()
        self.parser = PDFParser(file)
        self.laparams = LAParams(char_margin=char_margin, line_margin=line_margin, word_margin=word_margin)

        if PYTHON_3:
            self.doc = PDFDocument()
            self.parser.set_document(self.doc)
            self.doc.set_parser(self.parser)
            self.doc.initialize(password)
        else:
            self.doc = PDFDocument(self.parser, password)

        if not check_extractable or self.doc.is_extractable:
            self.resmgr = PDFResourceManager()
            self.device = TextConverter(self.resmgr, outfp=BytesIO(), laparams=self.laparams)
            self.interpreter = PDFPageInterpreter(
               self.resmgr, self.device)

            if PYTHON_3:
                page_generator = self.doc.get_pages()
            else:
                page_generator = PDFPage.create_pages(self.doc)

            for page in page_generator:
                self.append(self.interpreter.process_page(page))
            self.metadata = self.doc.info
        if just_text:
            self._cleanup()

    def _cleanup(self):
        """
        Frees lots of non-textual information, such as the fonts
        and images and the objects that were needed to parse the
        PDF.
        """
        self.device = None
        self.doc = None
        self.parser = None
        self.resmgr = None
        self.interpreter = None

    def text(self, clean=True, stringify=True):
        """
        Returns the text of the PDF as a single string.
        Options:

          :clean:
            Removes misc cruft, like lots of whitespace.
        """
        as_text = b''.join(self)
        if stringify and sys.version_info.major > 2:
            # Modern Python; detect encoding and cast to string
            guessed_encoding = chardet.detect(as_text)
            as_text = as_text.decode(guessed_encoding['encoding'])

        if clean:
            return utils.normalise_whitespace(as_text)
        else:
            return as_text
