#main.py
from app.core.pipeline.pipeline import run


def main():
    while True:
        user_input = input("Chat: ")

        if user_input.lower() == "exit":
            break

        response = run(user_input)
        print(f"AI: {response}")

if __name__ == "__main__":
    main()