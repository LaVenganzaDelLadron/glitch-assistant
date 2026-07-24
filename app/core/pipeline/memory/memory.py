#app/core/pipeline/memory/input.py

conversation = []

def load():
    return conversation

def save(user, assistant):
    conversation.append([user, assistant])