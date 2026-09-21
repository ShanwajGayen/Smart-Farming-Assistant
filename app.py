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
MODEL_DIR = os.path.join(BASE_DIR, "ai model")
MODEL_PATH = os.path.join(MODEL_DIR, "crop_disease_model.pth")
CLASS_PATH = os.path.join(BASE_DIR, "disease_classes.json")

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["JSON_SORT_KEYS"] = False
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
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

BEN_MAP = {
    "Apple___Apple_scab": "আপেল — স্ক্যাব রোগ",
    "Apple___Black_rot": "আপেল — ব্ল্যাক রট (কালো পচা)",
    "Apple___Cedar_apple_rust": "আপেল — সিডার অ্যাপেল রাস্ট (মরিচা)",
    "Apple___healthy": "আপেল — সুস্থ ও নিরোগ পাতা",
    "Blueberry___healthy": "ব্লুবেরি — সুস্থ পাতা",
    "Cherry_(including_sour)___Powdery_mildew": "চেরি — পাউডারি মিলডিউ (ছত্রাক)",
    "Cherry_(including_sour)___healthy": "চেরি — সুস্থ পাতা",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "ভুট্টা — ধূসর পাতার দাগ (সারকোস্পোরা)",
    "Corn_(maize)___Common_rust_": "ভুট্টা — সাধারণ রাস্ট (মরিচা রোগ)",
    "Corn_(maize)___Northern_Leaf_Blight": "ভুট্টা — নর্দান লিফ ব্লাইট (পাতাপোড়া রোগ)",
    "Corn_(maize)___healthy": "ভুট্টা — সুস্থ পাতা",
    "Grape___Black_rot": "আঙুর — ব্ল্যাক রট (কালো পচা রোগ)",
    "Grape___Esca_(Black_Measles)": "আঙুর — এসকা (কালো হাম রোগ)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "আঙুর — পাতা পোড়া রোগ (লিফ ব্লাইট)",
    "Grape___healthy": "আঙুর — সুস্থ পাতা",
    "Orange___Haunglongbing_(Citrus_greening)": "লেবু/কমলা — সাইট্রাস গ্রিনিং রোগ",
    "Peach___Bacterial_spot": "পীচ — ব্যাকটেরিয়াজনিত পাতার দাগ",
    "Peach___healthy": "পীচ — সুস্থ পাতা",
    "Pepper,_bell___Bacterial_spot": "ক্যাপসিকাম/মরিচ — ব্যাকটেরিয়াজনিত দাগ রোগ",
    "Pepper,_bell___healthy": "ক্যাপসিকাম/মরিচ — সুস্থ পাতা",
    "Potato___Early_blight": "আলু — আর্লি ব্লাইট (আগাম ধসা রোগ)",
    "Potato___Late_blight": "আলু — লেট ব্লাইট (নাবী ধসা রোগ)",
    "Potato___healthy": "আলু — সুস্থ পাতা",
    "Raspberry___healthy": "রাস্পবেরি — সুস্থ পাতা",
    "Soybean___healthy": "সয়াবিন — সুস্থ পাতা",
    "Squash___Powdery_mildew": "মিষ্টিকুমড়া/স্কোয়াশ — পাউডারি মিলডিউ",
    "Strawberry___Leaf_scorch": "স্ট্রবেরি — লিফ স্কর্চ (পাতা ঝলসানো রোগ)",
    "Strawberry___healthy": "স্ট্রবেরি — সুস্থ পাতা",
    "Tomato___Bacterial_spot": "টমেটো — ব্যাকটেরিয়াল স্পট (জীবাণু দাগ)",
    "Tomato___Early_blight": "টমেটো — আর্লি ব্লাইট (আগাম ধসা)",
    "Tomato___Late_blight": "টমেটো — লেট ব্লাইট (নাবী ধসা)",
    "Tomato___Leaf_Mold": "টমেটো — লিফ মোল্ড (পাতার ছত্রাক)",
    "Tomato___Septoria_leaf_spot": "টমেটো — সেপটোরিয়া পাতার দাগ",
    "Tomato___Spider_mites Two-spotted_spider_mite": "টমেটো — লাল মাকড়সা / স্পাইডার মাইট",
    "Tomato___Target_Spot": "টমেটো — টার্গেট স্পট দাগ",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "টমেটো — হলুদ পাতা কুঁকড়ানো ভাইরাস",
    "Tomato___Tomato_mosaic_virus": "টমেটো — মোজাইক ভাইরাস",
    "Tomato___healthy": "টমেটো — সুস্থ পাতা",
    "Rice___Brown_Spot": "ধান — বাদামী দাগ রোগ (ব্রাউন স্পট)",
    "Rice___Healthy": "ধান — সুস্থ ধান গাছ",
    "Rice___Leaf_Blast": "ধান — পাতা ব্লাস্ট রোগ",
    "Rice___Neck_Blast": "ধান — শীষ ব্লাস্ট (নেক ব্লাস্ট রোগ)"
}

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


def load_model():
    global model, model_loaded, num_classes, class_names, device
    if torch is None or models is None or nn is None or not os.path.exists(MODEL_PATH):
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


@app.route("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/api/config")
def app_config():
    return jsonify({
        "hasGeminiKey": bool(GEMINI_API_KEY),
        "modelReady": model_loaded,
        "classesCount": num_classes,
    })


@app.route("/api/remedy", methods=["POST"])
def remedy():
    payload = request.get_json(silent=True) or {}
    disease_name = str(payload.get("diseaseName") or "unknown crop condition")
    confidence = float(payload.get("confidence") or 0)
    language = str(payload.get("language") or "bn")

    if confidence < 15 or "not a plant" in disease_name.lower():
        fallback = "এই ছবিটিতে কোনো পরিষ্কার পাতা শনাক্ত করা যায়নি। দয়া করে ক্যামেরায় একটি একক পাতার স্পষ্ট ছবি তুলুন।"
        return jsonify({"success": True, "remedy": fallback})

    if GEMINI_API_KEY:
        try:
            prompt = (
                f"Act as a rural agricultural extension officer. The farmer's crop condition is: {disease_name}. "
                "Provide exactly 2 actionable, practical, organic and chemical treatment instructions in Bengali (বাংলা). "
                "Use simple language that an Indian farmer understands. Keep it concise."
            )
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            body_data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return jsonify({"success": True, "remedy": data["candidates"][0]["content"]["parts"][0]["text"].strip()})
        except Exception as e:
            print("Gemini API error:", e)

    fallback = f"আক্রান্ত পাতা অবিলম্বে ছেঁটে পরিষ্কার করুন এবং অনুমোদিত ছত্রাকনাশক (কপার অক্সিক্লোরাইড বা ম্যানকোজেব ২ গ্রাম/লিটার জলে) স্প্রে করুন।"
    return jsonify({"success": True, "remedy": fallback})


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
        image = ImageOps.exif_transpose(raw_img)
        if image.mode != "RGB":
            image = image.convert("RGB")

        image.thumbnail((800, 800), Image.Resampling.LANCZOS)
        tensor = image_transforms(image).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = model(tensor)
            probabilities = torch.softmax(outputs, dim=1)
            predicted_class_idx = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0, predicted_class_idx].item() * 100

        raw_class = class_names[predicted_class_idx]
        bengali_name = BEN_MAP.get(raw_class, raw_class.replace("___", " — ").replace("_", " "))
        english_name = raw_class.replace("___", " — ").replace("_", " ")

        top_k = min(5, len(class_names))
        top5_probs, top5_indices = torch.topk(probabilities[0], k=top_k)
        top5_predictions = [
            {
                "class_en": class_names[idx.item()].replace("___", " — ").replace("_", " "),
                "class_bn": BEN_MAP.get(class_names[idx.item()], class_names[idx.item()]),
                "confidence": round(prob.item() * 100, 1),
            }
            for prob, idx in zip(top5_probs, top5_indices)
        ]

        if confidence < 15:
            return jsonify({
                "success": True,
                "prediction_bn": "গাছ বা পাতা শনাক্ত করা যায়নি",
                "prediction_en": "Not a plant or leaf",
                "confidence": round(confidence, 1),
                "isNotPlantLeaf": True,
                "top5": top5_predictions,
            })

        return jsonify({
            "success": True,
            "prediction_bn": bengali_name,
            "prediction_en": english_name,
            "confidence": round(confidence, 1),
            "isNotPlantLeaf": False,
            "top5": top5_predictions,
        })
    except Exception as exc:
        return jsonify({"error": f"Error processing image: {str(exc)}"}), 500


@app.route("/<path:path>")
def serve_static(path):
    if path.startswith("api/"):
        return jsonify({"error": "API endpoint not found"}), 404
    return send_from_directory(PUBLIC_DIR, path)


if __name__ == "__main__":
    load_model()
    port = int(os.environ.get("PORT", "10000"))
    app.run(debug=False, host="0.0.0.0", port=port)
