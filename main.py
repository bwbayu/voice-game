import os
from dotenv import load_dotenv
from mistralai import Mistral

load_dotenv()

api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-large-latest"

client = Mistral(api_key=api_key)

chat_response = client.chat.complete(
    model = model,
    messages = [
        {
            "role": "user",
            "content": "How far is the moon from earth?",
        },
    ]
)