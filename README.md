# localai-chat

**Working: enough for me**


Very basic CLI chatbot for LocalAI, written in Python3.


*Please Note:*

This project was created for specific personal tasks. It will only be adjusted to the environment that I am using this in.


## Current features:
- Paste weblinks into the prompt and interact with just about any website that has text.
- Get transcripts from YouTube videos, and prompt on the content.
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content.
- Basic support for prompting on audio/video files.
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found. (With sources!)
- Automatically switch models (using your description of each model)


## Other features:
- Text-streaming for outputs
- Reply to conversations, load previous conversations and continue them
- Send preconfigured/custom cURL commands
- Stable Diffusion outputs
- Adjustable system prompt


## Planned features:
- File outputs


## Current dependencies:
- check requirements


## Setup:
- Use a basic completion template for your models, e.g.:

```
{{.Input}}

ASSISTANT: 
```


## Test environment:
- Ubuntu Server 22.04
- Nvidia Tesla M40 24GB, Cuda 12.4
- 2x Xeon E5-2660 v3
- Python 3.10.12
- LocalAI 2.10.2

