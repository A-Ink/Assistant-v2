# Alliance Terminal v2

A privacy-focused, locally hosted AI assistant tailored as a proactive, biologically aware scheduling coach. Styled around the *Mass Effect* universe, it optimizes your calendar natively on edge hardware using the professional, formal persona of an English Butler.

---

## ⚡ Quick Start (Windows 11)

1. **Deploy Terminal**
   Run the automated script to set up your environment and dependencies:
   ```powershell
   ./setup.ps1
   ```
2. **Requisition AI Cores**
   Download and optimize the models for your hardware:
   ```powershell
   python download_model.py
   ```
3. **Launch Interface**
   Start the Normandy UI and AI backend:
   ```powershell
   python main.py
   ```

---

## 🧠 System Architecture

The architecture is optimized for **Intel Core Ultra** (Meteor Lake/Lunar Lake) silicon, maximizing performance while remaining battery-conscious.

### 1. NPU-First Pipeline (OpenVINO GenAI)
The primary engine uses **OpenVINO GenAI 2025.x** to route 7B/8B parameter models strictly to the **NPU**. This minimizes CPU/GPU overhead and enables sub-10s cold starts via graph caching.

### 2. Hybrid Entity Extraction
We use `StructuredOutputConfig` to enforce a strict JSON schema. The AI identifies intent and extracts raw temporal data, while the **Python Mood Engine** handles the scheduling logic, conflict resolution, and priority math.

### 3. Vulkan GGUF Fallback
For devices without an NPU, the terminal supports the **Vulkan Engine** via `llama-cpp-python`, providing high-speed inference on Intel Arc and integrated GPUs.

---

## 🛠️ Performance & Features

- **Cold Start Optimization**: NPU/Vulkan graphs are compiled once and stored in `model_cache/`. Subsequent boots take <10s.
- **RAG Memory**: Persistent vector memory (ChromaDB) stores the "Commander Dossier" for personalized context.
- **Telemetry**: Real-time monitoring of System RAM and App-specific memory usage.
- **Mass Effect Persona**: Immersive feedback and lore-integrated scheduling recommendations.

---

## ⚙️ Technical Requirements

- **OS**: Windows 11
- **Python**: 3.12 (Managed via `setup.ps1`)
- **Hardware**: Intel Core Ultra (NPU) or Intel Arc/iGPU (Vulkan)
- **AI Core**: OpenVINO 2026.0.x
