from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, wait_for_db
from .routers import auth, admin, rtd, ezdfs, mypage

# Wait for DB to be ready
wait_for_db()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MSS Test Manager API", version="1.0.0")

# CORS Configuration
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:40203",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(rtd.router)
app.include_router(ezdfs.router)
app.include_router(mypage.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to MSS Test Manager API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
