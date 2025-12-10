import unittest
import os
from ingestion import parse_text, parse_html

class TestIngestion(unittest.TestCase):
    def test_parse_text(self):
        content = b"Hello World"
        self.assertEqual(parse_text(content), "Hello World")
        
    def test_parse_html(self):
        content = b"<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
        text = parse_html(content)
        self.assertIn("Title", text)
        self.assertIn("Paragraph", text)

if __name__ == '__main__':
    unittest.main()
