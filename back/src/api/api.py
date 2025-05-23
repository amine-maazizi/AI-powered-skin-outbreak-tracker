import sys
import os
import base64
import cv2
import numpy as np # Explicit import for ndarray check
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
import tempfile
import traceback
from typing import Optional, List, Dict # Cleaned up Optional import

sys.path.append('..')
from detection.score import analyze_skin_image
from correlation import analyse_acne_corr
# --- Rename 'profile.py' to 'user_profile.py' in your file system ---
# Then change the import below:
try:
    from ..db.user_profile_db import init_db, save_profile_to_db, get_profile_from_db
except ImportError:
    print("ERROR: Could not import from 'user_profile_db'.")

# --- Path Setup ---
# Get the directory containing the 'api' folder (assumes api.py is in 'src/api/')
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Get the directory containing the 'src' folder (the 'back' directory)
BACK_DIR = os.path.abspath(os.path.join(SRC_DIR, '..'))

# Add 'back' directory to sys.path to allow imports like 'tsa.module', 'detection.module'
# Only add if not already present to avoid duplicates
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)
    print(f"Added '{BACK_DIR}' to sys.path")

# --- Import other local modules wwith error handling ---
try:
    # Assuming analyze_acne_data is in 'back/tsa/analyse_acne_corr.py'
    from correlation.analyse_acne_corr import analyze_acne_data
except ImportError as e:
    print(f"ERROR: Could not import 'analyze_acne_data' from 'tsa'. Check path and file. Details: {e}")
    analyze_acne_data = None

try:
    # Assuming analyze_skin_image is in 'back/detection/score.py'
    from detection.score import analyze_skin_image
except ImportError as e:
    print(f"ERROR: Could not import 'analyze_skin_image' from 'detection.score'. Check path and file. Details: {e}")
    analyze_skin_image = None # Set to None if import fails

# --- FastAPI App Initialization ---
app = FastAPI(title="Acne Tracker Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"], # Allow Streamlit default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize database on startup ---
try:
    if init_db:
        init_db()
        print("Database initialized.")
    else:
        print("WARNING: init_db function not imported/available.")
except Exception as e:
    print(f"ERROR during database initialization: {e}")
    traceback.print_exc()

# --- Configuration ---
# Model path relative to the 'back' directory
MODEL_WEIGHTS_PATH = os.path.join(BACK_DIR,'src','detection', 'best.pt')

if not os.path.exists(MODEL_WEIGHTS_PATH):
    print(f"WARNING: Model file not found at expected path: {MODEL_WEIGHTS_PATH}")
    # Depending on requirements, you might want to raise an error here


# ---------------------------
# Pydantic Models (Keep as they were)
# ---------------------------
class Profile(BaseModel):
    user_id: str = "user_1"
    name: str
    dob: date
    height: float
    weight: float
    gender: Optional[str] = "Not Specified"

class AnalysisResponse(BaseModel):
    correlations: dict
    summary: str

class DetectionInfo(BaseModel):
    class_name: str
    confidence: float

class DetectionResponse(BaseModel):
    success: bool
    message: str
    severity_score: Optional[float] = None
    percentage_area: Optional[float] = None
    average_intensity: Optional[float] = None
    lesion_count: Optional[int] = None
    heatmap_image_base64: Optional[str] = None
    detections: Optional[List[DetectionInfo]] = None
    model_classes: Optional[Dict[int, str]] = None


# ---------------------------
# API Endpoints
# ---------------------------

@app.post("/profile/")
async def save_profile_endpoint(profile: Profile): # Renamed function slightly
    if not save_profile_to_db:
         raise HTTPException(status_code=501, detail="Profile saving feature not available.")
    try:
        save_profile_to_db(
            user_id=profile.user_id, name=profile.name, dob=profile.dob.isoformat(),
            height=profile.height, weight=profile.weight, gender=profile.gender
        )
        return {"message": "Profile saved successfully"}
    except Exception as e:
        print(f"Error saving profile for user {profile.user_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save profile.")


@app.get("/profile/{user_id}")
async def get_profile_endpoint(user_id: str): # Renamed function slightly
    if not get_profile_from_db:
        raise HTTPException(status_code=501, detail="Profile fetching feature not available.")
    try:
        profile_data = get_profile_from_db(user_id)
        if profile_data:
            # Ensure date objects are serializable if necessary, Pydantic usually handles date->str
            return profile_data
        else:
            raise HTTPException(status_code=404, detail="Profile not found")
    except HTTPException as e: # Re-raise client/not found errors
        raise e
    except Exception as e:
        print(f"Error fetching profile for user {user_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile.")


@app.get("/analyze/", response_model=AnalysisResponse)
async def analyze_endpoint(): # Renamed function slightly
    if not analyze_acne_data:
        raise HTTPException(status_code=501, detail="Correlation analysis feature not available.")
    try:
        # Database path relative to the 'back' directory
        db_path = os.path.join(BACK_DIR, '', 'acne_tracker.db')
        print(f"Analyzing database at: {db_path}")
        if not os.path.exists(db_path):
             raise FileNotFoundError(f"Database file not found at required path: {db_path}")

        correlations, summary = analyze_acne_data(db_path)
        return {"correlations": correlations, "summary": summary}
    except FileNotFoundError as e:
         # Raise 404 if DB file not found where expected
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error during correlation analysis: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed during correlation analysis: {str(e)}")


@app.post("/detect", response_model=DetectionResponse, summary="Detect skin conditions and score severity")
async def detect_skin_conditions(file: UploadFile = File(..., description="Image file for analysis (JPEG, PNG, BMP)")):
    """
    Accepts an image file, performs skin condition detection using a YOLOv8 model,
    calculates a severity score (using AcneAI formula based logic),
    generates a heatmap, and returns the results.
    """
    # Check if the core analysis function is available (due to import errors, etc.)
    if analyze_skin_image is None:
         print("CRITICAL: analyze_skin_image function is None, cannot process request.")
         raise HTTPException(status_code=501, detail="Detection analysis feature is not available.")

    # --- 1. Validate Input File Type ---
    allowed_types = ["image/jpeg", "image/png", "image/bmp"]
    if file.content_type not in allowed_types:
        print(f"Rejected file type: {file.content_type} for file: {file.filename}")
        raise HTTPException(
            status_code=415, # Unsupported Media Type
            detail=f"Invalid file type '{file.content_type}'. Please upload JPG, PNG, or BMP."
        )

    temp_image_path = None # Initialize for finally block
    try:
        # --- 2. Save Uploaded File Temporarily ---
        # Using delete=False and manual deletion in finally is necessary
        # because analyze_skin_image needs the path to exist when called.
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_image_file:
            content = await file.read()
            if not content:
                 raise HTTPException(status_code=400, detail="Received empty file content.")
            temp_image_file.write(content)
            temp_image_path = temp_image_file.name
        print(f"Temporary image saved to: {temp_image_path}")

        # --- 2.1 Resize Image to 640x640 ---
        img = cv2.imread(temp_image_path)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not read the uploaded image.")
        resized_img = cv2.resize(img, (640, 640))
        cv2.imwrite(temp_image_path, resized_img)
        print("Image resized to 640x640")

        # --- 3. Verify Model File Exists ---
        # Check just before potentially long analysis step
        if not os.path.exists(MODEL_WEIGHTS_PATH):
             print(f"CRITICAL ERROR: Model file missing at analysis time: {MODEL_WEIGHTS_PATH}")
             raise HTTPException(status_code=503, detail="Required analysis model file is currently unavailable.")

        # --- 4. Call Analysis Function ---
        # This now uses the version of analyze_skin_image calling calculate_acneai_score
        analysis_results = analyze_skin_image(
            model_path=MODEL_WEIGHTS_PATH,
            image_path=temp_image_path
            # Pass other parameters like conf_threshold if needed:
            # conf_threshold=0.3,
            # severity_map=CUSTOM_MAP, # etc.
        )

    except HTTPException as e:
        # Re-raise specific HTTP exceptions (e.g., 400, 415, 503)
        raise e
    except Exception as e:
        # Catch unexpected errors during file/analysis
        print(f"Error during file handling or analysis call for {file.filename}: {e}")
        traceback.print_exc()
        # Return a generic 500 error to the client
        raise HTTPException(status_code=500, detail="An error occurred while processing the image.")
    finally:
        # --- 5. Cleanup Temporary File ---
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
                print(f"Temporary image deleted: {temp_image_path}")
            except OSError as e:
                 print(f"Error deleting temporary file {temp_image_path}: {e}") # Log cleanup error but don't fail request

    # --- 6. Process Analysis Results ---
    if not analysis_results or not analysis_results.get('success'):
        error_message = analysis_results.get('message', 'Unknown analysis error') if analysis_results else "Analysis function returned invalid data"
        status_code = 500 # Default to Internal Server Error if analysis function fails
        if "not found" in error_message.lower():
            status_code = 404 # Indicate resource issue within analysis
        print(f"Analysis function failed or returned unsuccessful: {error_message}")
        raise HTTPException(status_code=status_code, detail=error_message)

    # --- 7. Encode Heatmap Image ---
    heatmap_base64 = None
    heatmap_data = analysis_results.get('heatmap_overlay_bgr')
    if heatmap_data is not None and isinstance(heatmap_data, np.ndarray):
        try:
            success, buffer = cv2.imencode('.png', heatmap_data) # Use PNG for lossless overlay
            if success:
                heatmap_base64 = base64.b64encode(buffer).decode('utf-8')
                print("Heatmap image successfully encoded to Base64.")
            else:
                 print("Warning: cv2.imencode failed for heatmap.") # Log warning
        except Exception as e:
            print(f"Error encoding heatmap image to Base64: {e}") # Log error
            traceback.print_exc()
            # Continue without heatmap if encoding fails

    # --- 8. Prepare and Return Successful Response ---
    # Construct the response using the Pydantic model
    response_data = DetectionResponse(
        success=True,
        message=analysis_results.get('message', 'Analysis successful.'),
        # Retrieve score and metrics calculated by analyze_skin_image
        severity_score=analysis_results.get('severity_score'),
        percentage_area=analysis_results.get('percentage_area'),
        average_intensity=analysis_results.get('average_intensity'),
        lesion_count=analysis_results.get('lesion_count'),
        heatmap_image_base64=heatmap_base64, # Include encoded heatmap string
        # Convert list of detection dicts to list of Pydantic models
        detections=[DetectionInfo(**det) for det in analysis_results.get('detections', [])],
        model_classes=analysis_results.get('model_classes')
    )
    return response_data


# --- Root endpoint ---
@app.get("/")
async def read_root():
    return {"message": "Acne Tracker Analysis API is running."}

# To run (save as api.py in src/api/, ensure you are in src/ directory):
# uvicorn api.api:app --reload --port 8000