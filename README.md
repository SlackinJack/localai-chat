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


### Parallel image requests setup (endless-mode only):

- Make the following model.yamls, and make changes to adapt this to your setup:

```
# configuration for gpu1
name: stablediffusion-gpu1
parameters:
  model: /path/to/stablediffusion/folder-gpu1/
backend: diffusers
f16: true
cuda: true
# etc...
```

```
# configuration for cpu1
name: stablediffusion-cpu1
parameters:
  model: /path/to/stablediffusion/folder-cpu1/
backend: diffusers
f16: false
cuda: false
# etc...
```

- You can use 'ln -s' to create copies of the model folder.

```
ln -s /path/to/stablediffusion/folder /path/to/stablediffusion/folder-cpu1
ln -s /path/to/stablediffusion/folder /path/to/stablediffusion/folder-cpu2
# and so on...
```

- Make sure to have the following in your LocalAI launcher,  and make changes to adapt this to your setup:

```
--parallel-requests=true --threads=4 --single-active-backend=false
```


## Test environment:
- Ubuntu Server 22.04
- Nvidia Tesla M40 24GB, Cuda 12.4
- 2x Xeon E5-2660 v3
- Python 3.10.12
- LocalAI 2.10.2

