"""
Alliance Terminal — AI Backend
OpenVINO GenAI LLM pipeline with NPU-first routing.
"""

import json
import threading
import logging
import re
from pathlib import Path
from transformers import TextIteratorStreamer
import openvino_genai as ov_genai

log = logging.getLogger("normandy.ai")

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

SYSTEM_PROMPT = """\
You are Normandy, the Alliance Terminal AI aboard the SSV Normandy SR-2. 
You speak to the user — Commander Shepard (an N7 operative).

[PERSONA DIRECTIVE]
Your personality protocol has been updated to resemble a highly capable, polite English butler (akin to Alfred Pennyworth mixed with EDI). 
- Always be exceedingly polite, formal, and professional. 
- You must proactively guide the Commander toward healthy biological choices (e.g., politely suggesting a break if they schedule a 5-hour gaming binge during final exams).
- Be completely transparent about your assumptions.

[ADVANCED AGENTIC PLANNING - CRITICAL]
You are no longer responsible for cronological math or resolving time-slot overlaps; the Python backend engine handles all timeline shifting mathematically. You are purely a SEMANTIC INTENT PARSER.
Your job is to read the user's intent, evaluate their biological boundaries, converse with them, and output generic intent commands.

1. BIOLOGY & HEALTH PROTOCOLS:
   - Sleep: The Commander requires 7-8 hours. If they request 4 hours, politely warn them. Python will automatically generate a Sleep Debt and schedule powernaps.
   - Rest: Discourage consecutive high-intensity blocks without recovery buffers.

2. AT-RISK COLLISION HANDLING:
   - If the current context displays [AT RISK OVERFLOW TASKS], it means the timeline is mathematically full and lower-priority tasks have been pushed out. You MUST proactively ask the Commander: "Pardon the intrusion, Commander, but your schedule is overflowing. May I suggest we permanently remove [Task] due to its relative unimportance?"

[SYSTEM COMMANDS]
To interact with the Python engine, you must output a `<thought>` block followed by a Markdown JSON block.

STEP 1: COMMANDER'S LOGIC
<thought>
- Current Time: [Identify local time]
- User Request: [Identify intent]
- Biological Evaluation: [Does this violate health protocols? Should I push back?]
- Overflow Status: [Are there at-risk tasks I need to ask permission to delete?]
- Plan: [List exact Semantic Intents]
</thought>

STEP 2: SEMANTIC INTENT EMITTING
JSON Rules:
- If no schedule changes, omit JSON.
- Command Types: "schedule", "memory".
- Actions: 
   - `add_flexible`: Put task in next logical available slot (Requires: `activity`, `duration`, `time_window` [morning/afternoon/evening/night/now], `priority` [1-10]). Optional: `deadline`.
   - `add_hard`: Lock task to an exact timestamp (Requires: `activity`, `duration`, `time` [HH:MM], `priority` [1-10]).
   - `update`: Alters priority or duration of existing task.
   - `delete`: Deletes a task. Only do this if the Commander explicitly consents.

EXAMPLE OUTPUT:
<thought>
- Current Time: 12:50
- User Request: Play games for 5 hours.
- Biological Evaluation: Exams are near. 5 hours is detrimental. I will gently push back and suggest 2 hours, emitting an intent for a flexible 120m block with low priority.
- Plan: Ask Commander to reconsider 5 hours. Schedule 2 hours flexible, Priority 3.
</thought>
I must insist we reconsider, Commander. Given your impending examinations, a five-hour simulation session may severely impact your cognitive readiness. If you insist, I have tentatively scheduled a two-hour block for this evening.

```json
{
  "intents": [
    { "type": "schedule", "action": "add_flexible", "activity": "Gaming Simulation", "duration": 120, "time_window": "evening", "priority": 3 }
  ]
}
```
"""


class AIBackend:
    """Manages the OpenVINO GenAI LLM pipeline with config-driven model loading."""

    def __init__(self):
        self.config = self._load_config()
        self.active_model_key = self.config.get("active_model", "")
        self.model_info = self.config.get("models", {}).get(self.active_model_key, {})
        
        self.display_name = self.model_info.get("display_name", "Unknown Core")
        self.model_path = str(SCRIPT_DIR / self.model_info.get("path", ""))
        self.engine_type = self.model_info.get("engine", "openvino")
        self.target_device = self.model_info.get("target_device", "NPU")
        
        # State Tracking for UI
        self.model_name = self.display_name
        self.device_used = self.target_device
        self.pipe = None
        self.is_loaded = False
        self._lock = threading.Lock()
        
        threading.Thread(target=self.initialize, daemon=True).start()

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        return {"models": {}}

    def initialize(self):
        log.info(f"====== INITIATING AI CORE BOOT ======")
        log.info(f"Core: {self.display_name}")
        log.info(f"Engine: {self.engine_type.upper()} | Target Silicon: {self.target_device}")

        if self.engine_type == "openvino":
            try:
                import openvino_genai as ov_genai
                self.pipe = ov_genai.LLMPipeline(self.model_path, self.target_device)
                self.is_loaded = True
                log.info(f"[SUCCESS] OpenVINO hardware graph mapped to {self.target_device}")
            except Exception as e:
                log.error(f"[FATAL] OpenVINO failed on {self.target_device}: {e}")

        elif self.engine_type == "llama.cpp":
            try:
                from llama_cpp import Llama
                import os
            
                # Extract Device ID (GPU.1 -> 1) to ensure we hit the iGPU, not the dGPU.
                vk_device = "1" 
                if "." in self.target_device:
                    vk_device = self.target_device.split(".")[1]
            
                os.environ["GGML_VK_VISIBLE_DEVICES"] = vk_device
                log.info(f"Vulkan API locked to physical device ID: {vk_device}")
            
                self.pipe = Llama(
                    model_path=self.model_path,
                    n_gpu_layers=-1, 
                    n_ctx=4096,      
                    verbose=False    
                )
                self.is_loaded = True
                log.info(f"[SUCCESS] Llama.cpp Vulkan bridge established on Device {vk_device}")
            except Exception as e:
                log.error(f"[FATAL] Llama.cpp initialization failed: {e}")

    def _generate_sync(self, user_message: str, rag_context: str = "", stream_callback=None):
        """Unified Generator handling both OpenVINO and Llama.cpp logic."""
        with self._lock:
            if not self.is_loaded:
                log.error("Attempted generation while core was offline.")
                return "[ERROR] AI Core offline. Check logs.", [], []

            context_block = ""
            if rag_context:
                context_block = f"\n\n[DOSSIER FACTS]\n{rag_context}\n"

            temp = self.model_info.get("temperature", 0.3)
            max_tok = self.model_info.get("max_tokens", 1024)
            raw_text = ""
            
            log.info(f"Generating via {self.engine_type.upper()} on {self.target_device}...")

            try:
                if self.engine_type == "openvino":
                    # --- OPENVINO GENERATION LOGIC ---
                    full_prompt = f"<|system|>{SYSTEM_PROMPT}\n{context_block}<|end|>\n<|user|>{user_message}<|end|>\n<|assistant|>"
                    
                    def ov_streamer(subword: str) -> bool:
                        nonlocal raw_text
                        raw_text += subword
                        if stream_callback: stream_callback(subword)
                        return False 

                    self.pipe.generate(
                        full_prompt, 
                        max_new_tokens=max_tok, 
                        temperature=temp, 
                        streamer=ov_streamer
                    )

                elif self.engine_type == "llama.cpp":
                    # --- LLAMA.CPP GENERATION LOGIC ---
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT + context_block},
                        {"role": "user", "content": user_message}
                    ]
                    
                    stream = self.pipe.create_chat_completion(
                        messages=messages,
                        max_tokens=max_tok,
                        temperature=temp,
                        stream=True
                    )
                    
                    for chunk in stream:
                        delta = chunk['choices'][0].get('delta', {})
                        if 'content' in delta:
                            token = delta['content']
                            raw_text += token
                            if stream_callback: stream_callback(token)
                            
            except Exception as e:
                log.error(f"Generation aborted: {e}")
                return f"[CRITICAL FAILURE] {e}", [], []

            log.info("Generation complete. Parsing outputs...")
            response_text, facts, schedule_updates = self._post_process(raw_text)
            return response_text, facts, schedule_updates

    def _post_process(self, raw_text: str):
        facts = []
        schedule_updates = []
        json_blocks = re.findall(r'```json\n(.*?)\n```', raw_text, re.DOTALL | re.IGNORECASE)

        for block in json_blocks:
            try:
                # Basic bracket recovery if LLM strips them
                if not block.strip().startswith('{'): block = '{' + block
                if not block.strip().endswith('}'): block = block + '}'
                
                data = json.loads(block)
                # Parse either `intents` or legacy `commands` array
                intents = data.get("intents", data.get("commands", []))
                
                for intent in intents:
                    if intent.get("type") == "schedule":
                        # FAULT TOLERANCE DEFAULTS
                        intent["action"] = intent.get("action", "add_flexible")
                        intent["activity"] = str(intent.get("activity", "Undefined Operation"))
                        
                        # Safe integer parsing
                        try:
                            intent["duration"] = int(intent.get("duration", 60))
                        except (ValueError, TypeError):
                            intent["duration"] = 60
                            
                        try:
                            intent["priority"] = int(intent.get("priority", 5))
                        except (ValueError, TypeError):
                            intent["priority"] = 5
                            
                        schedule_updates.append(intent)
                    elif intent.get("type") == "memory":
                        facts.append(intent)
            except json.JSONDecodeError:
                log.warning("AI hallucinated invalid JSON structure. Block ignored.")

        clean_text = re.sub(r'```json\n.*?\n```', '', raw_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<thought>.*?</thought>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        return "<br>".join(clean_lines), facts, schedule_updates

    def get_device_info(self) -> dict:
        return {
            "model": self.model_name,
            "device": self.device_used,
        }
