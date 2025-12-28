module.exports = {
  apps: [{
    name: "haiguitang",
    script: "python3",
    args: "-m uvicorn server.main:app --host 127.0.0.1 --port 8000",
    interpreter: "none"
  }]
}