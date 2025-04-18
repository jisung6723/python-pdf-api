
from src.core.file import PDFFile
from src.core.objects import PDFName, PDFString

file = PDFFile("testData/Gradient-based_learning_applied_to_document_recognition.pdf")

info = file.trailer.Info

print(info.value)
info[b'Creator'] = PDFString(file, b'jisung6723')

file.save('test.pdf')
