# Interactive citation-cache walkthrough

[Open the public demo](https://rag-citation-lab-oh6428.oh6428.chatgpt.site/) · [View the Wishket portfolio](https://www.wishket.com/partners/p/ohyoseok92/portfolio/322743)

This self-contained static site explains the Python demo's cache-key and citation-validation rules with a synthetic harbor-policy document. It first caches an answer citing 30 days, changes the document to 45 days, and repeats the same question. The naive cache returns the old citation; the source-versioned cache generates a new answer. All state stays in the browser. The page does not connect to Dragonfly, the Python API, or an LLM.

## Preview locally

From the repository root, run:

```sh
python -m http.server 4173 --bind 127.0.0.1 --directory web-demo
```

Then open `http://127.0.0.1:4173/`. HTTPS or localhost is needed for Web Crypto SHA-256.

`index.html`, `style.css`, and `app.js` are the deployed page source. `cover.html` is the source for the square Wishket cover. `screenshots/` contains the portfolio images. The deployed copy is maintained in a separate Sites source repository; this directory mirrors the published page at the time of this commit.
