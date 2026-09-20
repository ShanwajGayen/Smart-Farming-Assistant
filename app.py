import base64
import io
import json
import os
import urllib.request

try:
    import torch
    import torch.nn as nn
    from torchvision import models, transforms
except Exception:
    torch = None
    nn = None
    models = None
    transforms = None

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image

# Absolute base directory based on current file location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PUBLIC_DIR = os.path.join(BASE_DIR, "public")
MODEL_DIR = os.path.join(BASE_DIR, "ai model")
MODEL_PATH = os.path.join(MODEL_DIR, "crop_disease_model.pth")
CLASS_PATH = os.path.join(BASE_DIR, "disease_classes.json")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["JSON_SORT_KEYS"] = False

HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip() or os.getenv("HUGGING_FACE_API_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

class_names = []
num_classes = 0
model = None
model_loaded = False
device = torch.device("cpu") if torch is not None else "cpu"

if transforms is not None:
    image_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
else:
    image_transforms = None


def load_class_names():
    global class_names, num_classes
    if os.path.exists(CLASS_PATH):
        try:
            with open(CLASS_PATH, "r", encoding="utf-8") as file:
                class_names = json.load(file)
            num_classes = len(class_names)
            print(f"Loaded {num_classes} disease classes.")
            return
        except Exception as exc:
            print(f"Error reading disease_classes.json: {exc}")
    class_names = []
    num_classes = 0


load_class_names()


def load_model():
    global model, model_loaded, num_classes, class_names

    if torch is None or models is None or nn is None:
        print("PyTorch libraries not found.")
        model_loaded = False
        return False

    if not os.path.exists(MODEL_PATH):
        print(f"Model checkpoint not found at: {MODEL_PATH}")
        model_loaded = False
        return False

    try:
        checkpoint = torch.load(MODEL_PATH, map_location=device)
        checkpoint_num_classes = None

        if isinstance(checkpoint, dict):
            state_dict = checkpoint.get("state_dict", checkpoint)
            if "fc.weight" in state_dict:
                checkpoint_num_classes = state_dict["fc.weight"].shape[0]
        else:
            state_dict = checkpoint

        if checkpoint_num_classes is not None and num_classes != checkpoint_num_classes:
            num_classes = checkpoint_num_classes
            if not class_names or len(class_names) != num_classes:
                class_names = [f"class_{idx}" for idx in range(num_classes)]

        model = models.resnet18(weights=None)
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes if num_classes > 0 else 1000)
        model.load_state_dict(state_dict)
        model = model.to(device)
        model.eval()
        model_loaded = True
        print("Model loaded successfully on CPU!")
        return True
    except Exception as exc:
        print(f"Error loading model: {exc}")
        model_loaded = False
        return False


load_model()


def build_fallback_remedy(disease_name, confidence, language):
    safe_disease_name = disease_name.replace("___", " - ").replace("_", " ")
    normalized = safe_disease_name.lower()

    if "healthy" in normalized:
        if language == "bn":
            return f'"{safe_disease_name}" স্বাস্থ্যকর অবস্থায় আছে ({confidence:.1f}%)। ফসলের বৃদ্ধি বজায় রাখতে নিয়মিত পানি ও সুষম সার দিন।'
        return f'"{safe_disease_name}" appears healthy with {confidence:.1f}% confidence. Maintain consistent irrigation, balanced nutrition, and canopy hygiene.'

    if language == "bn":
        return f'"{safe_disease_name}" রোগ শনাক্ত হয়েছে ({confidence:.1f}%)। আক্রান্ত পাতা দ্রুত ছেঁটে ফেলুন, আর্দ্রতা নিয়ন্ত্রণে রাখুন এবং অনুমোদিত ছত্রাকনাশক স্প্রে করুন।'
    return f'Detected "{safe_disease_name}" with {confidence:.1f}% confidence. Prune affected foliage promptly, ensure proper ventilation, and apply an appropriate protective fungicide.'


def query_gemini_remedy(prompt_text):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 200}
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


@app.route("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "model_ready": model_loaded,
        "num_classes": num_classes,
        "device": str(device),
    })


@app.route("/api/config")
def app_config():
    provider = "gemini" if GEMINI_API_KEY else ("huggingface" if HF_API_TOKEN else "fallback")
    return jsonify({
        "hasHfKey": bool(HF_API_TOKEN),
        "hasGeminiKey": bool(GEMINI_API_KEY),
        "modelReady": model_loaded,
        "provider": provider,
    })


@app.route("/api/remedy", methods=["POST"])
def remedy():
    payload = request.get_json(silent=True) or {}
    disease_name = str(payload.get("diseaseName") or "unknown crop condition")
    confidence = float(payload.get("confidence") or 0)
    language = str(payload.get("language") or "en")
    safe_disease_name = disease_name.replace("___", " - ").replace("_", " ")

    if confidence < 30 or "not a plant" in safe_disease_name.lower() or "not a leaf" in safe_disease_name.lower():
        fallback = "এই ছবিটি পাতার বলে মনে হচ্ছে না। পরিষ্কার পাতার ছবি দিন।" if language == "bn" else "This image does not appear to be a crop leaf. Please upload a clear leaf image."
        return jsonify({"success": True, "remedy": fallback, "source": "validation"})

    target_lang = "Bengali" if language == "bn" else "English"
    prompt = f"Expert agronomy advice: Disease is {safe_disease_name} ({confidence:.1f}% confidence). Provide 2 short, practical management sentences in {target_lang}."

    if GEMINI_API_KEY:
        try:
            return jsonify({"success": True, "remedy": query_gemini_remedy(prompt), "source": "gemini"})
        except Exception as e:
            print(f"Gemini API error: {e}")

    return jsonify({"success": True, "remedy": build_fallback_remedy(safe_disease_name, confidence, language), "source": "fallback"})


@app.route("/api/predict", methods=["POST"])
def predict():
    if not model_loaded or image_transforms is None:
        return jsonify({"success": False, "error": "Model not loaded on host."}), 503

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    try:
        image = Image.open(file.stream).convert("RGB")
        preview_buffer = io.BytesIO()
        image.save(preview_buffer, format="JPEG", quality=70)
        preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode()

        tensor = image_transforms(image).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(tensor)
            probabilities = torch.softmax(outputs, dim=1)
            predicted_class_idx = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0, predicted_class_idx].item() * 100

        predicted_class = class_names[predicted_class_idx] if predicted_class_idx < len(class_names) else f"class_{predicted_class_idx}"
        top_k = min(5, len(class_names))
        top5_probs, top5_indices = torch.topk(probabilities[0], k=top_k)
        top5 = [
            {"class": class_names[i.item()] if i.item() < len(class_names) else f"class_{i.item()}", "confidence": p.item() * 100}
            for p, i in zip(top5_probs, top5_indices)
        ]

        is_not_plant = confidence < 30.0

        return jsonify({
            "success": True,
            "prediction": "Not a plant or leaf" if is_not_plant else predicted_class,
            "confidence": confidence,
            "isNotPlantLeaf": is_not_plant,
            "top5": top5,
            "image": f"data:image/jpeg;base64,{preview_base64}",
        })
    except Exception as exc:
        return jsonify({"error": f"Error processing image: {str(exc)}"}), 500


@app.route("/<path:path>")
def serve_static(path):
    if path.startswith("api/"):
        return jsonify({"error": "API endpoint not found"}), 404
    return send_from_directory(PUBLIC_DIR, path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
