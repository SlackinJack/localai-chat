# localai-chat

**Working: enough for me**


Very basic CLI chatbot for LocalAI, written in Python3.


*Please Note:*

This project was created for specific personal tasks.

It will only be adjusted to the environment that I am using this in.

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
- Use a completion template for your models, e.g.:

```
{{.Input}}
<|im_start|>assistant
```

## Planned feature priorities:
- (med) write new files
- (low) edit existing files
- (very low) file operations --> support other OS


## Test environment:
- Ubuntu Server 22.04
- Nvidia Tesla M40 24GB, Cuda 12.4
- 2x Xeon E5-2660 v3
- Python 3.10.12
- Model(s):
    - codellama-13b-instruct.Q4_K_S.gguf
    - Nous-Hermes-13B.Q4_K_M.gguf
    - samantha-1.2-mistral-7b-Q5_K_M.gguf
    - stable-diffusion-v1-5
- LocalAI 2.10.2, LocalAI 1.40.0 (occasionally tested)

