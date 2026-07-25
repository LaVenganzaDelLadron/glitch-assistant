from app.core.ai.factory import LLMFactory
from app.core.memory.conversation import ConversationMemory
from app.core.memory.project import ProjectMemory
from app.core.pipeline.context import PipelineContext
from app.core.pipeline.pipeline import Pipeline
from app.config.prompt import PromptLoader

memory = ConversationMemory()
memory.add_system(
    PromptLoader.load("chat")
)

context = PipelineContext(
    llm=LLMFactory.create(),
    conversation=memory,
    project=ProjectMemory(),
)

pipeline = Pipeline(context)

while True:
    prompt = input("You: ")

    if prompt == "exit":
        break

    response = pipeline.run(prompt)
    print("Content: ", response.content)