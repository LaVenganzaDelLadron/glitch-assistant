from app.core.ai.factory import LLMFactory
from app.core.memory.conversation import ConversationMemory
from app.core.memory.project import ProjectMemory
from app.core.pipeline.context import PipelineContext
from app.core.pipeline.pipeline import Pipeline
from app.tools import registry

memory = ConversationMemory()

context = PipelineContext(
    llm=LLMFactory.create(),
    conversation=memory,
    project=ProjectMemory(),
)

pipeline = Pipeline(context, registry=registry)

while True:
    print("\n\n")
    prompt = input("You: ")

    if prompt == "exit":
        break

    response = pipeline.run(prompt)
    print("Content: ", response.content)

