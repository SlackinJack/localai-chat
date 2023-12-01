# localai-chat

**Working: very slow**

Very barebones & basic front-end for LocalAI written in Python3

Current features (may change at any point):
- Paste weblinks into the prompt and interact with just about any website that has text.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Preliminal support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Generate responses only when appropriate (at least thats the goal anyway)
- Autodetect, and change models on-the-fly


Current dependencies (may change at any point):
- check requirements


Road map and targets (mostly for myself):
- add word-streaming...eventually
- main.py > triggers > openFile > support other OS (currently Ubuntu)
- utils.py > splitBySentenceLenght > differentiate sentence period vs numerical decimals
- search.py > getInfoFromWebsite > add timeout


Using uncensored-jordan-7b to test.
