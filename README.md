# localai-chat

**Working: enough for me**


Very barebones & basic front-end for LocalAI written in Python3


*Please Note:*

This was created explicitly for specific personal tasks that I myself am too lazy to do.

As such, it should only be treated as a patch-job/passion project.

(For now) it will only be updated according to my needs, and adjusted to the environment I am using this in.

Goals are only "nice to haves".


## Current features:
- Paste weblinks into the prompt and interact with just about any website that has text.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Preliminal support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Autodetect, and change models on-the-fly
- Text-streaming
- Reply to conversations, load previous conversations or make new ones


## Current dependencies:
- check requirements


## Road map and targets:
- (lowest priority) main.py > triggers > openFile > support other OS
- (???) output files
- (???) directly edit files
- (???) some sort of GUI


## Test environment:
- Ubuntu Server 22.04
- NVidia Quadro P2000 5GB, Cuda 12.3
- 2x Xeon X5650
- Python 3.10
- Model(s):
    - CatPPT-base-Q2_K
    - uncensored-jordan-7b.Q4_K_S
    - mistral-7b-instruct-v0.2-code-ft.Q4_K_S
    - Samantha-1.11-7b-ggml-model-q4_0
- LocalAI 1.40.0 (main), LocalAI 2.5.1 (occasionally tested)

