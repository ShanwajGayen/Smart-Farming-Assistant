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
from PIL import Image, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv_file()
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
MODEL_DIR = os.path.join(BASE_DIR, "ai model")
MODEL_PATH = os.path.join(MODEL_DIR, "crop_disease_model.pth")
CLASS_PATH = os.path.join(BASE_DIR, "disease_classes.json")

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["JSON_SORT_KEYS"] = False
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip() or os.getenv("HUGGING_FACE_API_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

DEFAULT_42_CLASSES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
    "Rice___Brown_Spot",
    "Rice___Healthy",
    "Rice___Leaf_Blast",
    "Rice___Neck_Blast"
]

class_names = DEFAULT_42_CLASSES
num_classes = len(class_names)
model = None
model_loaded = False
device = torch.device("cuda" if torch and torch.cuda.is_available() else "cpu") if torch is not None else "cpu"

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
                loaded = json.load(file)
                if isinstance(loaded, list) and len(loaded) > 0:
                    class_names = loaded
                    num_classes = len(class_names)
                    print(f"Loaded {num_classes} disease classes from {CLASS_PATH}")
                    return
        except Exception as exc:
            print(f"Error reading disease_classes.json: {exc}")

    class_names = DEFAULT_42_CLASSES
    num_classes = len(class_names)
    print(f"Using built-in {num_classes} classes.")


load_class_names()


def load_model():
    global model, model_loaded, num_classes, class_names, device

    if torch is None or models is None or nn is None:
        print("ML dependencies unavailable.")
        model_loaded = False
        return False

    if not os.path.exists(MODEL_PATH):
        print(f"Model file not found: {MODEL_PATH}")
        model_loaded = False
        return False

    try:
        checkpoint = torch.load(MODEL_PATH, map_location=device)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]

        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        model.load_state_dict(checkpoint)
        model = model.to(device)
        model.eval()
        model_loaded = True
        print("Model loaded successfully!")
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
        return f'"{safe_disease_name}" appears healthy with {confidence:.1f}% confidence. Maintain consistent irrigation, nutrition, and canopy hygiene.'

    disease_map = {
        "early blight": {
            "en": 'Detected "Early Blight" with {confidence:.1f}% confidence. Remove infected leaves immediately, increase spacing for airflow, and apply copper-based or Mancozeb fungicide according to label instructions.',
            "bn": '"Early Blight" রোগ শনাক্ত হয়েছে ({confidence:.1f}%)। আক্রান্ত পাতা দ্রুত তুলে ফেলুন এবং কপার বা মানকোজেব ছত্রাকনাশক নির্দেশিত মাত্রায় প্রয়োগ করুন।'
        },
        "late blight": {
            "en": 'Detected "Late Blight" with {confidence:.1f}% confidence. Remove diseased foliage promptly, reduce leaf wetness, and apply a systemic fungicide like Metalaxyl or Mancozeb.',
            "bn": '"Late Blight" রোগ শনাক্ত হয়েছে ({confidence:.1f}%)। আক্রান্ত পাতা দ্রুত তুলে ফেলুন, গাছের চারপাশে আর্দ্রতা কমান এবং মেটালাক্সিল বা মানকোজেব স্প্রে করুন।'
        },
        "powdery mildew": {
            "en": 'Detected "Powdery Mildew" with {confidence:.1f}% confidence. Improve air circulation, remove heavily infected shoots, and apply sulfur or potassium bicarbonate fungicide.',
            "bn": '"Powdery Mildew" শনাক্ত হয়েছে ({confidence:.1f}%)। বাতাস চলাচল বাড়ান এবং সালফার বা পটাশিয়াম বাইকার্বোনেট ছত্রাকনাশক ব্যবহার করুন।'
        },
        "bacterial spot": {
            "en": 'Detected "Bacterial Spot" with {confidence:.1f}% confidence. Avoid splashing water on leaves, sanitize pruning tools, and apply a copper-based bactericide.',
            "bn": '"Bacterial Spot" শনাক্ত হয়েছে ({confidence:.1f}%)। পাতায় পানি ছিটানো বন্ধ রাখুন এবং কপার ব্যাকটেরিসাইড ব্যবহার করুন।'
        },
        "leaf spot": {
            "en": 'Detected "Leaf Spot" with {confidence:.1f}% confidence. Remove affected leaves promptly, improve spacing, and apply a protective copper- or Mancozeb-based fungicide.',
            "bn": '"Leaf Spot" শনাক্ত হয়েছে ({confidence:.1f}%)। আক্রান্ত পাতা দ্রুত তুলে ফেলুন এবং কপার বা মানকোজেব ছত্রাকনাশক ব্যবহার করুন।'
        }
    }

    for key, advice in disease_map.items():
        if key in normalized:
            return advice["bn" if language == "bn" else "en"].format(confidence=confidence)

    if language == "bn":
        return f'"{safe_disease_name}" রোগ শনাক্ত হয়েছে ({confidence:.1f}%)। আক্রান্ত পাতা অপসারণ করুন এবং অনুমোদিত ছত্রাকনাশক স্প্রে করুন।'
    return f'Detected "{safe_disease_name}" with {confidence:.1f}% confidence. Remove infected foliage and apply an appropriate protective fungicide.'


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
    return jsonify({
        "hasHfKey": bool(HF_API_TOKEN),
        "hasGeminiKey": bool(GEMINI_API_KEY),
        "modelReady": model_loaded,
        "provider": "gemini" if GEMINI_API_KEY else ("huggingface" if HF_API_TOKEN else "fallback"),
    })


@app.route("/api/remedy", methods=["POST"])
def remedy():
    payload = request.get_json(silent=True) or {}
    disease_name = str(payload.get("diseaseName") or "unknown crop condition")
    confidence = float(payload.get("confidence") or 0)
    language = str(payload.get("language") or "en")
    safe_disease_name = disease_name.replace("___", " - ").replace("_", " ")

    if confidence < 15 or "not a plant" in safe_disease_name.lower() or "not a leaf" in safe_disease_name.lower():
        fallback = "এই ছবিটিতে গাছ বা পাতার বৈশিষ্ট্য শনাক্ত হয়নি। দয়া করে পরিষ্কার সবুজ পাতার ক্লোজ-আপ ছবি দিন।" if language == "bn" else "This image does not appear to be a plant leaf. Please upload a clear photo of a crop leaf."
        return jsonify({"success": True, "remedy": fallback, "source": "validation"})

    if GEMINI_API_KEY:
        try:
            target_lang = "Bengali" if language == "bn" else "English"
            prompt = f"Act as an expert agricultural scientist. Plant condition: {safe_disease_name} ({confidence:.1f}% confidence). Give 2 concise practical treatment steps in {target_lang}."
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            body_data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return jsonify({"success": True, "remedy": data["candidates"][0]["content"]["parts"][0]["text"].strip(), "source": "gemini"})
        except Exception as e:
            print("Gemini API error:", e)

    return jsonify({"success": True, "remedy": build_fallback_remedy(safe_disease_name, confidence, language), "source": "fallback"})


@app.route("/api/predict", methods=["POST"])
def predict():
    if not model_loaded:
        return jsonify({"success": False, "error": "Model not loaded"}), 503

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        raw_img = Image.open(file.stream)
        
        # 1. Correct mobile camera EXIF rotation so photos are upright
        image = ImageOps.exif_transpose(raw_img)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # 2. Bound image dimensions to prevent Render free-tier RAM crash
        image.thumbnail((800, 800), Image.Resampling.LANCZOS)

        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        image_base64 = __import__("base64").b64encode(image_buffer.getvalue()).decode()

        tensor = image_transforms(image).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(tensor)
            probabilities = torch.softmax(outputs, dim=1)
            predicted_class_idx = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0, predicted_class_idx].item() * 100

        predicted_class = class_names[predicted_class_idx] if predicted_class_idx < len(class_names) else f"class_{predicted_class_idx}"
        top_k = min(5, len(class_names))
        top5_probs, top5_indices = torch.topk(probabilities[0], k=top_k)
        top5_predictions = [
            {
                "class": class_names[idx.item()] if idx.item() < len(class_names) else f"class_{idx.item()}",
                "confidence": prob.item() * 100,
            }
            for prob, idx in zip(top5_probs, top5_indices)
        ]

        if confidence < 15:
            return jsonify({
                "success": True,
                "prediction": "Not a plant or leaf",
                "confidence": confidence,
                "isNotPlantLeaf": True,
                "top5": top5_predictions,
                "image": f"data:image/png;base64,{image_base64}",
            })

        return jsonify({
            "success": True,
            "prediction": predicted_class,
            "confidence": confidence,
            "isNotPlantLeaf": False,
            "top5": top5_predictions,
            "image": f"data:image/png;base64,{image_base64}",
        })
    except Exception as exc:
        return jsonify({"error": f"Error processing image: {str(exc)}"}), 500


@app.route("/<path:path>")
def serve_static(path):
    if path.startswith("api/"):
        return jsonify({"error": "API endpoint not found"}), 404
    return send_from_directory(PUBLIC_DIR, path)


if __name__ == "__main__":
    print("Loading model...")
    load_model()
    port = int(os.environ.get("PORT", "10000"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(debug=False, host=host, port=port)
