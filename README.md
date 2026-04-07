# Restaurant Agentic Customer Service

Welcome to the **Restaurant Agentic Customer Service** project! This project serves as a robust backend for a restaurant management and customer service system, powered by **FastAPI**, **SQLAlchemy** (using PostgreSQL), and enriched with AI agentic workflows via **LangChain** and **LangGraph**.

## 🌟 Features
* **RESTful APIs**: Comprehensive CRUD endpoints for Users, Menu Items, Orders, Order Items, Deliveries, and Transactions.
* **Repository Pattern**: Clean abstraction of database queries using SQLAlchemy.
* **Intelligent Agents**: `my_agent/` directory handles AI-driven workflows to automate tasks like order taking, QA, and customer service using LLMs.
* **Interactive Docs**: Auto-generated Swagger UI and ReDoc to easily test APIs.

---

## 🛠️ Prerequisites
Before running or contributing to this project, ensure you have the following installed:
* **Python 3.10+** (Preferably Python 3.12 managed via conda/venv)
* **PostgreSQL** database active and running.

---

## 🚀 Setup & Installation

**1. Clone the repository**
```bash
git clone <repository_url>
cd restaurant_agentic_customer_service
```

**2. Set up the Virtual Environment**
If you are using `conda`:
```bash
conda create -n venv python=3.12
conda activate ./venv
```
Or using built-in `venv`:
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows
# OR
source venv/bin/activate      # On Mac/Linux
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Configuration**
Check `app/core/config.py` for environment variables. You can create a `.env` file at the root of the project to override the default values:
```env
APP_NAME="Agentic Restaurant Customer Service"
DEBUG=True
DATABASE_URL="postgresql://postgres:your_password@localhost:5432/restaurant_db"
SECRET_KEY="your-secret-key-change-in-production"
```

---

## 🏃 Running the Application

To run the FastAPI server with live-reloading:

```bash
uvicorn app.main:app --reload
```

* Once the server is running, the API will be available at: http://127.0.0.1:8000
* **API Documentation (Swagger UI)**: http://127.0.0.1:8000/docs
* **Alternative Docs (ReDoc)**: http://127.0.0.1:8000/redoc

> **Note on Database Tables**: The app uses `Base.metadata.create_all(bind=engine)` on startup, which automatically creates any missing tables in your PostgreSQL database dynamically.

---

## 📁 Project Structure

```bash
.
├── app/
│   ├── api/            # API routers (v1 setup)
│   ├── core/           # Configs, Security, and Database setup
│   ├── migrations/     # Alembic configurations (if using db migrations later)
│   ├── models/         # SQLAlchemy ORM models (Database Tables)
│   ├── my_agent/       # LangChain / LangGraph Agentic Workflows
│   │   ├── agents/     # AI intelligent agents
│   │   ├── nodes/      # Graph execution nodes
│   │   ├── states/     # State tracking definitions
│   │   ├── tools/      # Tools available for the agent
│   │   └── workflow.py # Main graph builder
│   ├── repositories/   # Abstraction layer for DB queries
│   ├── schemas/        # Pydantic models for request/response validation
│   ├── services/       # Core business logic orchestrating repositories
│   ├── tests/          # Pytest files
│   └── main.py         # FastAPI application instance
│
├── frontend/           # React frontend built with Vite
└── requirements.txt    # Python dependencies
```

---

## 🤝 Contributing

When contributing to this project, please follow these guidelines:
1. **Branching**: Create a feature branch off of `main` (`git checkout -b feature/xyz`).
2. **Code Quality**: Keep routes strictly to HTTP logic, and use `app/repositories` for database logic and `app/services` for business logic.
3. **Validation**: Ensure any changes reflect correctly in Pydantic `app/schemas` mapping.
4. **Testing**: Run tests using `pytest` once they are populated.

Happy coding! 🍽️🤖
