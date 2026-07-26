# Token Optimization Implementation Plan

## Status Tracking
- [x] Step 1: Enhance ConversationMemory with token estimation & trimming
- [x] Step 2: Create ContextBuilder utility (NEW file)
- [x] Step 3: Update GroqProvider with token budget, max_tokens, logging
- [x] Step 4: Update Executor to use ContextBuilder & pass max_tokens
- [x] Step 5: Update Pipeline to pass task info for max_tokens
- [x] Testing: Verify logging, trimming, and functionality

## Information Gathered

**Current Architecture:**
- `app/core/pipeline/pipeline.py` → `Pipeline.run()` routes prompts and calls `Executor.execute()`
- `app/core/pipeline/executor.py` → `Executor._execute_tool_loop()` runs the tool-calling loop
- `app/core/ai/groq.py` → `GroqProvider.generate()` builds messages and calls LLM
- `app/core/memory/conversation.py` → `ConversationMemory` stores messages in a deque (already has `max_messages`)
- `app/core/utils/output_compressor.py` → Already has compression but applied per-tool in executor
- `app/application.py` → Creates pipeline with `ConversationMemory(max_messages=20)`
- `app/config/settings.py` → Already has `DEFAULT_MAX_CONTEXT_TOKENS`, `DEFAULT_MAX_HISTORY_MESSAGES`, etc.
- `app/config/prompt.py` → `PromptLoader.load()` loads a single prompt by name
- No database, no vector DB, no RAG

**Issues to fix:**
1. System prompt is duplicated — stored in conversation memory AND prepended in GroqProvider
2. No context size estimation/budget enforcement before LLM calls
3. No token usage logging after responses
4. No configurable `max_tokens` per task in LLM calls
5. Conversation trimming is basic (deque maxlen only)

## Plan

### Step 1: Enhance ConversationMemory with token estimation & trimming
- Add `estimated_tokens()` method to `ConversationMemory`
- Add `trim_to_fit(max_tokens, reserve_tokens)` method that removes oldest messages until within budget
- Keep messages() returning list[Message]

### Step 2: Create a ContextBuilder utility
- New file: `app/core/pipeline/context_builder.py`
- `build_messages(system_prompt, conversation, tool_outputs, current_user_message)` 
- Builds the message list in order: system, recent conversation (trimmed), compressed tool outputs, current user message

### Step 3: Update GroqProvider.generate() with token budget, max_tokens, and logging
- Accept `max_tokens` parameter (default reasonable per task)
- Accept `max_context_tokens` parameter
- Before calling LLM, estimate context size and trim if needed
- After response, log: prompt_tokens, completion_tokens, total_tokens
- Remove logic that skips system messages (context_builder handles dedup)

### Step 4: Update Executor with token optimization
- Pass `max_tokens` to LLM based on task type
- Use ContextBuilder before calling LLM
- Pass max_context_tokens from settings

### Step 5: Update Pipeline to pass task info for max_tokens selection

### Step 6: Update application.py default max_messages if needed

## Files to edit:
1. `app/core/memory/conversation.py` - Add token estimation & trimming
2. `app/core/pipeline/context_builder.py` - NEW file
3. `app/core/ai/groq.py` - Token budget, max_tokens, logging
4. `app/core/pipeline/executor.py` - Use ContextBuilder, pass max_tokens
5. `app/core/pipeline/pipeline.py` - Pass task info for max_tokens

## Followup:
- Test with existing CLI interface
- Verify token logging appears in console
- Verify old messages get trimmed when context exceeds limit

