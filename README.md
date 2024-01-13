# localai-chat

**Working: enough for me**

Very barebones & basic front-end for LocalAI written in Python3


*Please Note:
This was created explicitly for specific personal tasks that I myself am too lazy to do.
As such, it should only be treated as a patch-job/passion project.
It will only be updated according to my needs, or adjusted to the environment I am using this in.
Goals are only "nice to haves".*


## Current features (may change at any point):
- Paste weblinks into the prompt and interact with just about any website that has text.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Preliminal support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Autodetect, and change models on-the-fly
- Text-streaming
- Reply to conversations, load previous conversations or make new ones


## Current dependencies (may change at any point):
- check requirements


## Road map and targets (mostly for myself):
- (mid priority) file operations to-and-from server
- (low priority) utils.py > splitBySentenceLenght > differentiate sentence period vs numerical decimals
- (lowest priority) main.py > triggers > openFile > support other OS


## Test environment:
- Ubuntu Server 22.04
- NVidia Quadro P2000 5GB, Cuda 12.3
- Xeon X5650
- Python 3.10
- Model(s): uncensored-jordan-7b.Q4_K_S, mistral-7b-instruct-v0.2-code-ft.Q4_K_S, Samantha-1.11-7b-ggml-model-q4_0
- LocalAI 1.40.0 (main), LocalAI 2.5.1

