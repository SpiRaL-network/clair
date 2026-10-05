# Composants tiers

La licence MIT de Clair s'applique à son code source original. Les bibliothèques,
moteurs, runtimes et modèles téléchargés ne sont pas inclus dans ce dépôt et
conservent leurs licences respectives. Installer Clair ne transfère pas la
propriété de ces composants.

Principales sources :

| Composant | Rôle | Source et licence |
| --- | --- | --- |
| faster-whisper | Transcription | [Dépôt et licence MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| CTranslate2 | Exécution de Whisper | [Dépôt et licence](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| Whisper large-v3 | Poids du modèle de transcription | [Fiche et fichiers](https://huggingface.co/Systran/faster-whisper-large-v3) |
| llama.cpp | Exécution des modèles GGUF | [Dépôt et licence MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |
| PyAudioWPatch / PortAudio | Capture audio Windows | [Licence et attributions](https://github.com/s0d3s/PyAudioWPatch/blob/master/LICENSE.txt) |
| Python | Runtime autonome | [Licence Python](https://docs.python.org/3/license.html) |
| Composants NVIDIA CUDA/cuDNN/cuBLAS | Accélération NVIDIA | Licences NVIDIA livrées avec les paquets et archives téléchargés ; [CUDA Toolkit](https://docs.nvidia.com/cuda/eula/index.html) |
| Bibliothèques Python | API, audio, validation et tests | Versions dans `requirements.lock.txt`, licences dans les métadonnées et fichiers des distributions installées |

Les modèles GGUF proviennent des dépôts [Unsloth](https://huggingface.co/unsloth)
et [bartowski](https://huggingface.co/bartowski). Chaque entrée de
`models-catalog.json` pointe vers sa fiche. Ces fiches identifient les modèles
originaux, leurs licences et les quantifications. Les familles récentes :
[Qwen3.5](https://huggingface.co/Qwen/Qwen3.5-4B),
[Qwen3.8](https://huggingface.co/Qwen/Qwen3.8-27B) et
[Gemma 4](https://ai.google.dev/gemma/docs/releases).

Si vous redistribuez une installation contenant les dépendances ou les poids,
conservez les avis, licences et conditions fournis avec ces composants. Le dépôt
source seul ne contient ni les poids, ni les DLL/EXE, ni les enregistrements.
