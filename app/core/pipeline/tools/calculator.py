#app/core/pipeline/tools/calculator.py

def execute(text):
    expression = text.replace("calculate", "").strip()
    try:
        answer = eval(expression)
        print(f"ANSWER: {answer}")
    except Exception as e:
        print(f"ERROR: {e}")