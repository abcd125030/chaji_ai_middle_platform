# 12-Factor Agents: Patterns of Reliable LLM Applications
## By Dex Horthy (HumanLayer) - AI Engineer Presentation

---

## Executive Summary

Dex Horthy presented "12-Factor Agents: Patterns of reliable LLM applications" based on interviews with over 100 founders, AI engineers, CTOs, and practitioners who have successfully built agents in production generating significant revenue. The framework, inspired by Heroku's 12-Factor App methodology, provides a practical blueprint for building LLM-powered software that's robust, maintainable, and production-ready.

The key insight: **Most successful production AI agents aren't magical autonomous beings — they're well-engineered software systems that leverage LLMs for specific, controlled transformations.**

---

## Background & Context

### The Problem
- Most AI agent implementations hit a 70-80% quality ceiling
- The last 20% becomes a debugging nightmare with teams stuck reverse-engineering prompts
- Agents often hallucinate steps, loop infinitely, or fail to meet reliability standards
- Pushing past 80% often means rebuilding from scratch

### The Research
- Interviewed 100+ startup founders and AI engineers building production agents
- Focused on teams with agents deployed to enterprise making $100K+ to millions in revenue
- Found consistent patterns among successful implementations
- GitHub repository reached top of Hacker News, tracking toward 10K stars

### Key Finding
The teams succeeding with agents aren't using the most complex frameworks. They understand that **agents are just software**, and software engineering principles still apply.

---

## The 12-Factor Agents Framework (Actually 13 Factors)

### Core Philosophy
- LLMs are best at one thing: converting natural language to structured data (JSON)
- Everything else is regular software engineering
- Treat AI agents as software components, not magical black boxes
- Apply proven engineering practices to make them production-ready

---

## The Complete 12 (+1) Factors

### Factor 1: Natural Language to Tool Calls
**Principle**: Use LLMs to convert natural language into structured tool calls, then execute those tools deterministically.

**Example**: 
```
Natural Language: "Create a payment link for $750 to Jeff for sponsoring the february AI tinkerers meetup"

Structured Output:
{
  "function": {
    "name": "create_payment_link",
    "parameters": {
      "amount": 750,
      "customer": "cust_128934ddasf9",
      "product": "prod_8675309",
      "price": "prc_09874329fds",
      "quantity": 1,
      "memo": "Hey Jeff - see below for the payment link for the february ai tinkerers meetup"
    }
  }
}
```

**Implementation**:
```python
# The LLM takes natural language and returns structured JSON
# Your deterministic code handles the execution
if tool_call.name == "create_payment_link":
    result = stripe.payment_links.create(**tool_call.parameters)
    return result
```

---

### Factor 2: Own Your Prompts
**Principle**: Write your own prompts as first-class code rather than relying on opaque agent frameworks.

**Key Points**:
- Treat prompts as code, not one-off strings
- Version-control your prompts and templates
- Avoid "black box" prompt engineering libraries
- Maintain full visibility and control

**Why It Matters**: 
> "Your prompts are the primary interface between your application logic and the LLM."

**Benefits**:
- Full control over agent behavior
- Easy testing and evaluation
- Transparent debugging
- Rapid iteration

---

### Factor 3: Own Your Context Window
**Principle**: Take full control of what context you send to the LLM rather than relying on standard message formats.

**Core Insight**: 
> "At any given point, your input to an LLM in an agent is 'here's what's happened so far, what's the next step'"

**Context Engineering Includes**:
- Prompts and instructions
- Retrieved documents (RAG)
- Past state, tool calls, and results
- Related conversation history
- Structured output instructions

**Custom Context Format Example**:
Instead of standard message format, create optimized structures:
```python
context = {
    "current_state": {...},
    "available_tools": [...],
    "constraints": {...},
    "history": [...],
    "objective": "..."
}
```

---

### Factor 4: Tools are Structured Outputs
**Principle**: Treat tool calls as structured JSON outputs that trigger deterministic code, not magic functions.

**Pattern**:
1. LLM outputs structured JSON
2. Deterministic code executes appropriate action
3. Results fed back into context

**Example**:
```python
class CreateIssue:
    intent: "create_issue"
    issue: Issue

class SearchIssues:
    intent: "search_issues"
    query: str
    what_youre_looking_for: str

# Execution
if nextStep.intent == 'create_payment_link':
    stripe.paymentlinks.create(nextStep.parameters)
elif nextStep.intent == 'wait_for_a_while': 
    # handle differently
else:
    # handle unknown tool
```

---

### Factor 5: Unify Execution State and Business State
**Principle**: Avoid separating business state from execution state — keep them unified when possible.

**Definitions**:
- **Execution state**: current step, next step, waiting status, retry counts
- **Business state**: what's happened in the workflow (messages, tool calls, results)

**Benefit**: You can infer all execution state from the context window, simplifying architecture.

---

### Factor 6: Launch/Pause/Resume with Simple APIs
**Principle**: Build simple APIs that allow agents to be launched, paused, and resumed from external triggers.

**Requirements**:
- Easy launch via API
- Ability to pause during long operations
- Resume from webhooks without deep integration
- Clean state management

**Use Cases**:
- Waiting for human approval
- Long-running operations
- External event triggers

---

### Factor 7: Contact Humans with Tool Calls
**Principle**: Treat human interaction as just another structured tool call rather than a special case.

**Implementation**:
```python
class RequestHumanInput:
    intent: "request_human_input"
    question: str
    context: str
    options: Options

# In agent loop
if nextStep.intent == 'request_human_input':
    thread.events.append({
        type: 'human_input_requested',
        data: nextStep
    })
    await notify_human(nextStep, thread_id)
    return  # Break loop and wait for response
```

---

### Factor 8: Own Your Control Flow
**Principle**: Build custom control structures rather than relying on generic agent loops.

**Custom Control Examples**:
- Request clarification → break loop, wait for human
- Fetch data → append to context, continue
- High-stakes operation → request approval

**Benefits**:
- Summarization/caching of results
- LLM-as-judge on outputs
- Context window management
- Logging and metrics
- Rate limiting
- Durable sleep/pause

---

### Factor 9: Compact Errors into Context Window
**Principle**: Turn errors into context for the LLM to enable self-healing behavior.

**Implementation**:
```python
consecutive_errors = 0
while True:
    try:
        result = await handle_next_step(thread, next_step)
        consecutive_errors = 0
    except Exception as e:
        consecutive_errors += 1
        if consecutive_errors < 3:
            thread["events"].append({
                "type": 'error',
                "data": format_error(e),
            })
            # LLM can see error and adjust
        else:
            # escalate or break
```

**Benefits**:
- Self-healing capabilities
- Continued operation despite failures
- Better error handling

---

### Factor 10: Small, Focused Agents
**Principle**: Build agents that handle 3-20 steps max rather than monolithic agents.

**Key Insight**: 
> "As context grows, LLMs are more likely to get lost or lose focus"

**Benefits**:
1. Manageable context windows
2. Clear responsibilities
3. Better reliability
4. Easier testing
5. Improved debugging

**Future-Proofing**: As LLMs improve, agent scope can gradually expand while maintaining reliability.

---

### Factor 11: Trigger from Anywhere
**Principle**: Enable agents to be triggered and respond via Slack, email, SMS, etc.

**Benefits**:
- Meet users where they are
- Enable event-driven agents
- Support high-stakes operations with human oversight
- Create digital coworkers

**Use Cases**:
- Outer loop agents (work for hours, contact humans at critical points)
- Cross-platform communication
- Asynchronous workflows

---

### Factor 12: Make Your Agent a Stateless Reducer
**Principle**: Design agents as pure functions that take previous state and return new state.

**Functional Approach**:
```
agent(current_state, new_input) → new_state
```

**Benefits**:
- Predictable behavior
- Easy testing
- Clear state management
- Functional programming principles

---

### Factor 13 (Appendix): Pre-Fetch All Context You Might Need
**Principle**: Proactively gather context deterministically rather than making the LLM fetch it.

**Key Quote**: 
> "If you already know what tools you'll want the model to call, just call them DETERMINISTICALLY and let the model do the hard part of figuring out how to use their outputs."

**Evolution**:
1. ❌ Ask model to fetch context separately
2. ✅ Pre-fetch context and include in prompt
3. ✅✅ Fully integrate context retrieval into workflow

---

## Implementation Philosophy

### Core Tenets

1. **JSON Extraction is Foundation**
   - The most magical thing LLMs can do is convert natural language to structured data
   - Everything else is regular software engineering

2. **Context Engineering > Prompt Engineering**
   - Focus on what goes into the context window
   - Quality of context determines quality of output

3. **Agents are Software Components**
   - Not magical autonomous beings
   - Apply standard engineering practices
   - Maintain modularity, observability, robustness

4. **Start Small, Expand Gradually**
   - Begin with focused micro-agents
   - Expand scope as LLM capabilities improve
   - Maintain reliability throughout

---

## Real-World Impact

### Success Metrics
- Framework reached top of Hacker News for entire day
- GitHub repository tracking toward 10K stars
- Adopted by teams building million-dollar revenue agents
- Resonated with 100+ production practitioners

### Key Differentiator
Teams succeeding with agents aren't using the most complex frameworks. They understand that:
- Agents are just software
- Engineering principles still apply
- Reliability comes from good architecture, not magic

---

## Practical Applications

### When to Use This Framework
- Building production AI systems
- Need reliability above 80% success rate
- Deploying to enterprise customers
- Generating significant revenue
- Requiring auditability and control

### What You'll Achieve
- Push past the 70-80% quality ceiling
- Avoid debugging nightmares
- Build maintainable systems
- Create reliable production agents
- Scale with confidence

---

## Historical Context: Brief History of Software

The framework includes a philosophical perspective on software evolution:

1. **Traditional "Loop Until Solved" Approaches are Flawed**
   - Context window limitations cause agents to get "lost"
   - Even with longer windows, focused prompts work better

2. **Micro Agents are the Solution**
   - Small, focused workflow components
   - Within larger deterministic systems
   - Strategic AI integration, not replacement

3. **Core Components of Effective Agents**:
   - Prompt defining behavior and tools
   - Switch statement for tool handling
   - Accumulated context tracking
   - Control loop for progression

---

## Key Takeaways

### For Engineers
1. **Own Your Stack**: Don't outsource critical components to opaque frameworks
2. **Think in Patterns**: Apply the 12 factors as patterns, not rigid rules
3. **Start Simple**: Begin with basic implementations, expand as needed
4. **Measure Everything**: Observability is crucial for production systems

### For Organizations
1. **AI-Native ≠ Abandoning Engineering**: Don't throw out decades of wisdom
2. **Incremental Adoption**: Start with small agents, expand scope gradually
3. **Focus on Reliability**: 99% reliable beats 100% autonomous
4. **Human-in-the-Loop**: Design for human oversight from the start

### The Bottom Line
> "The fastest way to get high-quality AI software in the hands of customers is to take small, modular concepts from agent building and incorporate them into existing products."

---

## Resources & References

### Official Resources
- **GitHub Repository**: [github.com/humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents)
- **HumanLayer**: [humanlayer.dev](https://humanlayer.dev)
- **Author**: Dex Horthy (@dexhorthy)

### Presentations
- AI Engineer World's Fair (June 2024)
- Agents in Production 2025
- MLOps Community Video

### Community
- Hacker News Discussion (Top page for full day)
- Multiple blog analyses and implementations
- Growing ecosystem of practitioners

---

## About the Author

**Dex Horthy** is the founder of HumanLayer, a platform for building reliable AI agents with human oversight. His work is based on:
- Interviews with 100+ production practitioners
- Building and deploying production agents
- Analyzing patterns in successful implementations
- Creating tools for human-agent interaction

---

## Conclusion

The 12-Factor Agents framework represents a paradigm shift in how we think about AI agents. Rather than chasing magical autonomous systems, it advocates for well-engineered software that leverages LLMs strategically. 

The message is clear: **Build reliable systems today with proven engineering practices, not promises of future AI magic.**

As Dex Horthy emphasizes: *"Most 'AI agents' that actually succeed in production aren't magical autonomous beings at all – they're mostly well-engineered traditional software, with LLM capabilities carefully sprinkled in at key points."*

This framework provides the blueprint for joining the ranks of successful production AI implementations, moving beyond the 80% ceiling to deliver real value to customers.

---

*Last Updated: Based on presentations and documentation through 2025*
*Framework Version: 1.0 (includes 13 factors)*