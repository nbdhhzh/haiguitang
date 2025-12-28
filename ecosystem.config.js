module.exports = {
  apps : [{
    name: "haiguitang",
    script: "uvicorn",
    args: "server.main:app --host 127.0.0.1 --port 8080",
    interpreter: "python3",
  }]
}
