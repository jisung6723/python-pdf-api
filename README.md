
# python-pdf-api 

A pure Python library to **parse, edit, and write PDF files** from scratch, with full control over objects, streams, cross-reference tables, and incremental updates.

## ✨ Features

- 🧠 **Lazy-loading** of PDF objects
- 🔍 Complete support for **XRef tables and streams**
- 🔄 **Incremental update** mechanism
- 🧱 Object-level access to:
  - `IndirectRef`, `XRefEntry`, `PDFDict`, `PDFStream`
  - Specialized structures like `Trailer`, `StreamExtent`
- 🧰 Custom **filter decoding/encoding** (e.g. FlateDecode)
- 🛠️ Object stream (ObjStm) and stream filter handling in progress

## 🎯 Roadmap

- [x] Basic XRef parsing
- [x] Trailer parsing
- [x] Indirect object resolution
- [x] Stream decoding (Flate)
- [ ] Full Object Stream support
- [ ] Encryption/Decryption
- [ ] Incremental updates (writing)

## 🧑‍💻 Author

Made with ☕ and curiosity by [jisung6723](https://github.com/your-username)

---
