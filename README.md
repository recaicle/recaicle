# recAIcle ♻️

AI-powered waste sorting app — point your camera at any trash and instantly know which bin it goes in, based on local regulations.

**Supported countries:** 🇹🇼 Taiwan · 🇯🇵 Japan · 🇫🇷 France

## Deploy on Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo → set main file as `app.py`
4. Under **Advanced settings → Secrets**, add:

```toml
GEMINI_API_KEY = "AIza..."
```

5. Deploy — done!

## Local development

```bash
pip install -r requirements.txt

# Create .streamlit/secrets.toml
mkdir -p .streamlit
echo 'GEMINI_API_KEY = "AIza..."' > .streamlit/secrets.toml

streamlit run app.py
```
