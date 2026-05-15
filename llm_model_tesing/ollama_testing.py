from openai import OpenAI

# Connect to local Ollama (same OpenAI SDK!)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-needed"  # Ollama doesn't need a key
)

response = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": "mera POS bill print nahi ho raha"}]
)
print(response.choices[0].message.content)