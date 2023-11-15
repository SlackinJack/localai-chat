# localai-chat

**Working: Very broken and extremely slow**

Very barebones basic front-end for LocalAI written in Python3

Current features (may change at any point):
- Paste weblinks into the prompt and interact with just about any website that has text. (very slow)
- Read a PDF locally (very slow), or read any text-based file (default) and tells you a summary.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Generate responses only when appropriate (at least thats the goal anyway)
- Autodetect, and change models on-the-fly


Current dependencies (may change at any point):
- BeautifulSoup4
- duckduckgo_search
- PyPDF2
- readability_lxml
- termcolor


Using uncensored-jordan-7b, samantha-7b to test.
