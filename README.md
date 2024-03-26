# localai-chat

**Working: enough for me**


Very basic CLI tool for LocalAI, written in Python3


*Please Note:*

This was created for specific personal tasks.

(For now) it will only be updated according to my needs, and adjusted to the environment I am using this in.

Goals are only "nice to haves".


## Current features:
- Paste weblinks into the prompt and interact with just about any website that has text.
- Get transcripts from YouTube videos, and prompt on the content.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Basic support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Auto-switch models on-the-fly
- Text-streaming for outputs
- Reply to conversations, load previous conversations and continue them
- Send preconfigured/custom cURL commands


## Current dependencies:
- check requirements


## Setup:
- Use a completion chat template for your models.


## Road map and targets:
- (???) output files
- (???) directly edit files
- (lowest priority) main.py > triggers > openFile > support other OS


## Test environment:
- Ubuntu Server 22.04
- ~~Nvidia Tesla M40 24GB, Cuda 12.4~~
- 2x Xeon E5-2660 v3
- Python 3.10
- Model(s):
    - CatPPT-base-Mistral-7B-Instruct-v0.1.Q5_K_S.gguf
    - speechless-code-mistral-7b-v1.0.Q5_K_S.gguf
    - samantha-1.2-mistral-7b-Q5_K_S.gguf
- LocalAI 2.10.1

