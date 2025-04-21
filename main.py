
from src.core.file import PDFFile
from src.core.objects import *
from src.core.stream import Filter, Stream


file = PDFFile('test.pdf')

# with open("result", "wb") as f:
#     for key in file.xref.table:
#         obj = file.xref.table[key].read()
#         if isinstance(obj, PDFStream):
#             s = Stream(obj)
#             try:
#                 s.decode()
#             except Exception as e:
#                 f.write(str(e).encode('utf-8'))
#                 f.write(str(obj.extent.value).encode('utf-8'))

stream = file.resolve(IndRef(file, 266, 0))
s = Stream(stream)
s.decode().plot()
