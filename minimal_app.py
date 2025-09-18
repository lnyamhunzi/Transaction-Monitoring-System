from fastapi import FastAPI

app = FastAPI()

@app.get("/test-route")
async def test_route():
    return {"message": "Test route is working!"}
