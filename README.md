# Cloud Pulse AI: AI-FinOps-Advisor

Cloud Pulse AI is an intelligent, Django-powered Cloud FinOps Cost Optimization Advisor. Designed for cloud administrators, DevOps engineers, and financial managers, it helps organizations track, analyze, forecast, and optimize their cloud environment spend. 

By leveraging machine learning and data analysis (including anomaly detection and hourly forecasting models), Cloud Pulse AI empowers teams to identify anomalous spending spikes, forecast future costs, and receive automated recommendations to eliminate waste.

---

## 🚀 Key Features

*   **Cost Dashboard:** Visually track and monitor daily and hourly cloud spend metrics.
*   **AI-Driven Anomaly Detection:** Identify unusual cost patterns or sudden resource spend surges.
*   **Predictive Forecasting:** Machine learning models trained on historical usage project hourly and future billing.
*   **Smart Cost Recommendations:** Tailored suggestions (e.g., resizing instances, terminating idle resources) based on cloud resource metrics.
*   **User Management:** Secure user authentication (registration, login, profile setup, forgot/reset password) with email notifications.
*   **Deployment Ready:** Configured for quick setup and deployment on platforms like Render.

---

## 🛠️ Tech Stack

*   **Backend Framework:** Django (Python)
*   **Data Science & ML:** `pandas`, `numpy`, `scikit-learn`, `scipy`, `joblib`
*   **Frontend:** HTML5, CSS3, JavaScript (with responsive/interactive layouts)
*   **Server Configuration:** Gunicorn, WhiteNoise (for static file handling)
*   **Database:** SQLite (default/development)

---

## ⚙️ Configuration & Environment Variables

The project uses a `.env` file to manage configuration. You can copy the template file to get started:

```bash
cp .env.example .env
```

Ensure the following variables are configured:

| Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `SECRET_KEY` | Django secret key for cryptographic signing | *Generate a secure random string* |
| `DEBUG` | Django debug mode status (`True` or `False`) | `True` |
| `EMAIL_HOST_USER` | Email account username for outbound emails | `your_email@example.com` |
| `EMAIL_HOST_PASSWORD` | App-specific email password | `your_app_password` |

---

## 💻 Local Installation & Setup

Follow these steps to run the application locally on your machine.

### Prerequisites
*   Python 3.10+
*   `pip` (Python package manager)

### 1. Clone the Repository
```bash
git clone https://github.com/SHIV4347/Cloud-Pulse-AI.git
cd Cloud-Pulse-AI
```

### 2. Create and Activate a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv AI_Finops_venv
.\AI_Finops_venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
python3 -m venv AI_Finops_venv
source AI_Finops_venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment File
Create your local environment configuration file:
```bash
cp .env.example .env
```
Open `.env` and fill in the required keys.

### 5. Apply Database Migrations
Create and migrate the database schema:
```bash
python manage.py migrate
```

### 6. Run the Development Server
Start the local server:
```bash
python manage.py runserver
```
Once started, access the application in your browser at `http://127.0.0.1:8000/`.

---

## 🌐 Production Deployment (Render)

This repository includes a `render.yaml` template and a `build.sh` script for zero-config deployments on **Render**.

1. Connect your GitHub repository to Render.
2. Render will automatically detect the `render.yaml` configuration.
3. Configure the environment variables (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`) in your Render dashboard under the service configuration.
4. During deployment, the build script will automatically run migrations and collect static files:
   ```bash
   # build.sh execution flow:
   pip install -r requirements.txt
   python manage.py collectstatic --noinput
   python manage.py migrate
   ```
