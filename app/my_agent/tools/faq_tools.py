import json 
from openai import OpenAI
import numpy as np

from app.core.config import get_settings
from app.models.faq import FAQ
settings = get_settings()

client=OpenAI(api_key=settings.OPENAI_API_KEY)



def get_embedding(text: str):
    if isinstance(text, dict):
        text = text.get("question") or text.get("text") or ""

    if not isinstance(text, str):
        text = str(text)

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
def cosine_similarity(a, b):
    a=np.array(a)
    b=np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_best_faq(question:str, db):
    user_embedding=get_embedding(question)
    faqs=db.query(FAQ).all()
    best_faq=None
    best_score=-1

    for faq in faqs:
        try:
            faq_embedding = json.loads(faq.embedding)
        except (TypeError, json.JSONDecodeError):
            continue  # Skip if embedding is invalid

        score = cosine_similarity(user_embedding, faq_embedding)
        if score > best_score:
            best_score = score
            best_faq = faq
    return best_faq, best_score

def generate_answer(question: str, faq_answer: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful restaurant assistant. "
                    "Use the provided FAQ answer to respond. "
                    "You may rephrase it to sound natural and user-friendly, "
                    "but do not change the meaning."
                )
            },
            {
                "role": "user",
                "content": f"""
User question: {question}

FAQ answer:
{faq_answer}

Return a natural response to the user.
"""
            }
        ]
    )

    return response.choices[0].message.content