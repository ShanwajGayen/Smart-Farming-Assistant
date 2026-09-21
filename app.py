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
from PIL import Image, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
MODEL_PATH = os.path.join(BASE_DIR, "ai model", "crop_disease_model.pth")
CLASS_PATH = os.path.join(BASE_DIR, "disease_classes.json")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

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
device = torch.device("cpu")

if transforms is not None:
    image_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
else:
    image_transforms = None


def init_classes():
    global class_names, num_classes
    if os.path.exists(CLASS_PATH):
        try:
            with open(CLASS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list) and len(loaded) > 0:
                    class_names = loaded
                    num_classes = len(class_names)
                    print(f"Loaded {num_classes} classes from {CLASS_PATH}")
                    return
        except Exception as e:
            print(f"Notice: Using default classes ({e})")
    print(f"Using built-in {num_classes} classes.")


init_classes()


def load_model():
    global model, model_loaded
    if not os.path.exists(MODEL_PATH):
        print(f"Model not found at: {MODEL_PATH}")
        return False
    try:
        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        state_dict = torch.load(MODEL_PATH, map_location=device)
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        model_loaded = True
        print("Model loaded successfully on CPU!")
        return True
    except Exception as exc:
        print(f"Error loading model: {exc}")
        return False


load_model()


@app.route("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/api/config")
def config():
    return jsonify({
        "hasGeminiKey": bool(GEMINI_API_KEY),
        "modelReady": model_loaded,
        "classesCount": num_classes,
    })


@app.route("/api/predict", methods=["POST"])
def predict():
    if not model_loaded:
        return jsonify({"success": False, "error": "Model not loaded"}), 503
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    try:
        raw_img = Image.open(file.stream)
        # Automatic EXIF rotation fix for mobile camera shots
        img = ImageOps.exif_transpose(raw_img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Memory bounds to guarantee stability on 512MB RAM
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)

        tensor = image_transforms(img).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(tensor)
            probs = torch.softmax(outputs, dim=1)[0]
            top_probs, top_indices = torch.topk(probs, k=min(5, num_classes))

        top5 = [
            {"class": class_names[idx.item()], "confidence": round(prob.item() * 100, 2)}
            for prob, idx in zip(top_probs, top_indices)
        ]

        best_conf = top5[0]["confidence"]
        best_class = top5[0]["class"]

        # 15% threshold tailored for phone cameras in field lighting
        is_not_plant = best_conf < 15.0

        return jsonify({
            "success": True,
            "prediction": "Not a plant or leaf" if is_not_plant else best_class,
            "confidence": best_conf,
            "isNotPlantLeaf": is_not_plant,
            "top5": top5,
        })
    except Exception as exc:
        print(f"Prediction error: {exc}")
        return jsonify({"error": f"Image processing failed: {str(exc)}"}), 500


@app.route("/api/remedy", methods=["POST"])
def remedy():
    data = request.get_json(silent=True) or {}
    disease = str(data.get("diseaseName", "")).replace("___", " - ").replace("_", " ")
    lang = data.get("language", "en")

    if not disease or "not a plant" in disease.lower():
        msg = "এই ছবিটি স্পষ্ট নয়। পাতার পরিষ্কার ক্লোজ-আপ ছবি দিন।" if lang == "bn" else "Please upload a clear close-up picture of a single crop leaf."
        return jsonify({"success": True, "remedy": msg})

    if GEMINI_API_KEY:
        try:
            target_lang = "Bengali" if lang == "bn" else "English"
            prompt = f"Act as an agricultural expert. Diagnosed crop disease: {disease}. Give 2 practical treatment and management recommendations in {target_lang}."
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as res:
                result = json.loads(res.read().decode("utf-8"))
                return jsonify({"success": True, "remedy": result["candidates"][0]["content"]["parts"][0]["text"].strip()})
        except Exception as e:
            print("Gemini API error:", e)

    fallback = "আক্রান্ত পাতা অবিলম্বে অপসারণ করুন এবং অনুমোদিত ছত্রাকনাশক স্প্রে করুন।" if lang == "bn" else "Prune heavily infected leaves and apply an appropriate protective organic or copper fungicide."
    return jsonify({"success": True, "remedy": fallback})


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(PUBLIC_DIR, path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
