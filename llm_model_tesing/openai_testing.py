from openai import OpenAI
client = OpenAI(api_key="sk-your-key")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "mera POS bill print nahi ho raha"}]
)
print(response.choices[0].message.content)