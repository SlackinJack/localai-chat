# localai-chat

**Working: enough for me**


Very basic CLI chatbot for LocalAI, written in Python3.


*Please Note:*

This project was created for specific personal tasks. It will only be adjusted to the environment that I am using this in.


## Current features:
- Paste weblinks into the prompt and interact with just about any website that has text
- Get transcripts from YouTube videos, and prompt on the content
- Read PDFs, DOCX, PPTX, or other files (as raw text), and prompt on the content
- Basic support for prompting on audio/video files
- Search duckduckgo based on generated search terms from your prompt, then answer your prompt based on what it found (with sources)
- Automatically switch models (using your description of each model)


## Other features:
- Text-streaming for outputs
- Reply to conversations, load previous conversations and continue them
- Send cURL commands
- Image outputs (single or endless)
- Adjustable system prompt
- Use time, location data (IP-based) to get updated and localized information
- Utilize both CPU and GPU for image outputs (endless-mode)


## Planned features:
- Image-to-Image
- Image-to-Text (vision, scan for text)
- STT/TTS
- Function-generated file outputs


## Current dependencies:
- check requirements


## Setup:
- Completion template:

```
{{.Input}}

ASSISTANT: 
```

- Roles configuration:

```
roles:
  assistant: 'ASSISTANT'
  system: 'SYSTEM'
  user: 'USER'
```

- If you want to use both CPU and GPU for endless image generation mode:
  - Make a copy your GPU model.yaml, paste as model-cpu.yaml, eg.:

```
name: stablediffusion
parameters:
  model: /path/to/stablediffusion/folder/
backend: diffusers
f16: true
cuda: true
```

  - Then make CPU-specific changes to it, eg.:

```
name: stablediffusion-cpu
parameters:
  model: /path/to/stablediffusion/folder/
backend: diffusers
f16: false
cuda: false
```

  - Make sure to have the following in your LocalAI launcher,  and make changes as necessary to adapt this to your system/configuration:

```
"--parallel-requests=true --threads=4 --single-active-backend=false"
```

## Test environment:
- Ubuntu Server 22.04
- Nvidia Tesla M40 24GB, Cuda 12.4
- 2x Xeon E5-2660 v3
- Python 3.10.12
- LocalAI 2.10.2

