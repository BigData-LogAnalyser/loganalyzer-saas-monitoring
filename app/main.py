from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def home():
    return """
    <!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LogAnalyzer</title>
      </head>
      <body>
        <h1>LogAnalyzer</h1>
        <p>L'application Flask fonctionne.</p>
        <p>Configuration de l'environnement — SCRUM-13.</p>
      </body>
    </html>
    """


@app.get("/health")
def health():
    return jsonify(status="ok", service="webapp")