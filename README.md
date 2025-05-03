# AI-powered-skin-outbreak-tracker
AI-powered system that helps users better understand and manage their skin outbreaks 

## Setup

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Authentication

Before running the code, you must export your Hugging Face access token as an environment variable so that the `from_pretrained` calls can authenticate:

```bash
# macOS/Linux (bash or zsh)
export HF_TOKEN="your_hf_access_token"

# Windows PowerShell
setx HF_TOKEN "your_hf_access_token"

```

### Product Search API

To enable product recommendations, you need a [SerpAPI](https://serpapi.com/) key for Google Shopping search:

```bash
# macOS/Linux (bash or zsh)
export SERPAPI_KEY="your_serpapi_key"

# Windows PowerShell
setx SERPAPI_KEY "your_serpapi_key"

```

## Backend Setup and Launch

1. Navigate to the backend directory:
```bash
cd back
```

2. Create and activate a virtual environment:
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
PYTHONPATH=$PYTHONPATH:. python3 src/db/create_db.py
```
In Windows:
```
$env:PYTHONPATH = "$env:PYTHONPATH;."; python src/db/create_db.py
```

5. Start the backend server:
```bash
PYTHONPATH=$PYTHONPATH:. uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

In Windows:
```bash
$env:PYTHONPATH = "$env:PYTHONPATH;."; uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at: http://localhost:8000
- API documentation: http://localhost:8000/docs
- Alternative API documentation: http://localhost:8000/redoc

## Frontend Setup and Launch

1. Open a new terminal and navigate to the frontend directory:
```bash
cd front
```

2. Create and activate a virtual environment:
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the frontend server:
```bash
streamlit run src/skin_tracker_app.py
```

The frontend application will be available at: http://localhost:8501

## Testing the Application

1. The backend API should be running on http://localhost:8000
2. The frontend application should be running on http://localhost:8501
3. Use the test user ID: `test_user_1` to log in
4. You can:
   - Upload photos for skin analysis
   - Track lifestyle factors
   - View your dashboard
   - Generate personalized skin plans with product recommendations

## Troubleshooting

If you encounter any issues:

1. Make sure both backend and frontend servers are running
2. Check that the Hugging Face token is properly set
3. Check that the SerpAPI key is properly set for product recommendations
4. Verify that the database was initialized correctly
5. Check the terminal output for any error messages
6. Try restarting both servers if needed

## API Endpoints

The backend provides the following main endpoints:

- `POST /api/v1/detect/`: Upload and analyze skin photos
- `GET /api/v1/timeseries/{user_id}`: Get timeseries data
- `POST /api/v1/timeseries/`: Save lifestyle data
- `GET /api/v1/profile/{user_id}`: Get user profile
- `POST /api/v1/profile/`: Save user profile
- `POST /api/v1/skin-plan/generate`: Generate personalized skin plan with product recommendations
