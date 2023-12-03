# localai-chat

**Working: enough for me**

Very barebones & basic front-end for LocalAI written in Python3

## Current features (may change at any point):
- Paste weblinks into the prompt and interact with just about any website that has text.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Preliminal support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Generate responses only when appropriate (at least thats the goal anyway)
- Autodetect, and change models on-the-fly
- Text-streaming


## Current dependencies (may change at any point):
- check requirements


## Road map and targets (mostly for myself):
- main.py > triggers > openFile > support other OS (currently Ubuntu)
- utils.py > splitBySentenceLenght > differentiate sentence period vs numerical decimals
- search.py > getInfoFromWebsite > add timeout
- add conversation context (reply)


## Test environment:
- Ubuntu Server 22.04
- NVidia Quadro P2000 5GB, Cuda 12.3
- Xeon X5650
- Python 3.10
- Model(s): uncensored-jordan-7b.Q5_K_M
